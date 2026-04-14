"""
Motor de Execução do Trade Bot MT5
====================================

Este módulo contém a classe TradeBotEngine, responsável por toda a lógica
de execução de ordens no MetaTrader 5:

- Conexão e desconexão com o MT5
- Busca de barras históricas e preço atual
- Criação de ordens limite
- Cancelamento de ordens pendentes
- Fechamento parcial de posições
- Monitoramento de ordens pendentes e posições abertas
- Gestão de risco diária (stops máximos, operações simultâneas, PnL diário)
- Janela de horário e fechamento forçado
- Break-even automático
- Loop principal do robô

A lógica de detecção de sinal é completamente desacoplada em estratégias
separadas (trade_bot/strategies/). O engine recebe a estratégia ativa via
injeção de dependência no construtor.

Uso:
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig
    from trade_bot.strategies.ma200_rejection import MA200RejectionStrategy, MA200Config

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=MA200RejectionStrategy(),
        strategy_config=MA200Config(),
    )
    engine.run()
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, time as dtime
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from trade_bot.models import BotConfig, Direction, Trade, TradeStatus
from trade_bot.strategies.base import BaseStrategy
from trade_bot.db import BotDatabase
from trade_bot.discord_notifier import DiscordNotifier

logger = logging.getLogger(__name__)


class SymbolGate:
    """
    Interface de bloqueio por símbolo usada pelo orquestrador multi-estratégia.

    Implementada por BotOrchestrator; quando o engine opera em modo standalone
    (sem orquestrador), o parâmetro symbol_gate é None e o gate é ignorado.

    O método principal é try_acquire_symbol, que faz check+reserve atomicamente
    sob um único lock, eliminando a race condition TOCTOU entre is_symbol_free
    e register_trade.
    """

    def try_acquire_symbol(self, symbol: str) -> bool:
        """
        Verifica se o símbolo está livre e, caso esteja, reserva-o
        atomicamente. Retorna True se adquirido, False se ocupado.
        Deve ser chamado antes de enviar a ordem ao MT5.
        """
        raise NotImplementedError

    def release_trade(self, symbol: str) -> None:
        """
        Libera a reserva do símbolo. Deve ser chamado ao fechar ou cancelar
        um trade, ou quando order_send falha após uma aquisição bem-sucedida.
        """
        raise NotImplementedError


class TradeBotEngine:
    """Motor principal do robô: execução de ordens, gestão de risco e loop de monitoramento."""

    def __init__(
        self,
        config: BotConfig,
        strategy: BaseStrategy,
        strategy_config: object,
        strategy_name: Optional[str] = None,
        db: Optional[BotDatabase] = None,
        skip_connect: bool = False,
        symbol_gate: Optional[SymbolGate] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Parâmetros:
            config: Configurações gerais (símbolo, lote, parciais, risco).
            strategy: Instância de uma estratégia que herda de BaseStrategy.
            strategy_config: Dataclass de configuração específica da estratégia.
            strategy_name: Chave da estratégia (ex.: 'ma200_rejection') — gravada no banco.
            db: Instância opcional de BotDatabase para sincronização com o painel.
            skip_connect: Se True, pula mt5.initialize() no run() (usado pelo orquestrador).
            symbol_gate: Gate de exclusão por símbolo (usado pelo BotOrchestrador).
            stop_event: Evento de parada compartilhado com o orquestrador.
        """
        self.config = config
        self.strategy = strategy
        self.strategy_config = strategy_config
        self._strategy_name: Optional[str] = strategy_name
        self._db: Optional[BotDatabase] = db
        self._skip_connect: bool = skip_connect
        self._symbol_gate: Optional[SymbolGate] = symbol_gate
        self._stop_event: Optional[threading.Event] = stop_event

        self.trades: list[Trade] = []
        self._trade_id_counter: int = 0
        self._daily_stops: int = 0
        self._daily_pnl: float = 0.0
        self._last_reset_date: date = date.today()
        self._is_running: bool = False
        self._force_closed_today: bool = False
        self._discord: DiscordNotifier = DiscordNotifier(db=db)

        tf_map = {
            1: mt5.TIMEFRAME_M1,
            5: mt5.TIMEFRAME_M5,
            15: mt5.TIMEFRAME_M15,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1,
        }
        self._mt5_timeframe = tf_map.get(config.timeframe_minutes, mt5.TIMEFRAME_M5)

    # ------------------------------------------------------------------
    # Gestão de risco e horário
    # ------------------------------------------------------------------
    def _reset_daily_stats_if_needed(self) -> None:
        today = date.today()
        if today != self._last_reset_date:
            logger.info("Novo dia: resetando contadores diários.")
            self._daily_stops = 0
            self._daily_pnl = 0.0
            self._force_closed_today = False
            self._last_reset_date = today

    def _open_trades_count(self) -> int:
        return sum(1 for t in self.trades if t.status == TradeStatus.OPEN)

    def _pending_trades_count(self) -> int:
        return sum(1 for t in self.trades if t.status == TradeStatus.PENDING)

    def _is_blocked(self) -> bool:
        """Retorna True se o robô está bloqueado para abrir novas operações."""
        if self._daily_stops >= self.config.max_daily_stops:
            return True
        active = self._open_trades_count() + self._pending_trades_count()
        if active >= self.config.max_open_trades:
            return True
        if (
            self.config.max_daily_loss_pts is not None
            and self._daily_pnl <= -self.config.max_daily_loss_pts
        ):
            return True
        if (
            self.config.max_daily_profit_pts is not None
            and self._daily_pnl >= self.config.max_daily_profit_pts
        ):
            return True
        return False

    @staticmethod
    def _parse_hhmm(value: str) -> Optional[dtime]:
        """Converte string 'HH:MM' para datetime.time. Retorna None e loga erro se inválida."""
        try:
            parts = value.strip().split(":")
            if len(parts) != 2:
                raise ValueError("Formato esperado HH:MM")
            h, m = int(parts[0]), int(parts[1])
            return dtime(h, m)
        except Exception as exc:
            logger.error("Horário inválido '%s': %s. Parâmetro ignorado.", value, exc)
            return None

    def _is_outside_trading_window(self) -> bool:
        """Retorna True se o horário atual está fora da janela permitida para novas entradas."""
        start_str = self.config.trading_start_time
        end_str = self.config.trading_end_time
        if not start_str and not end_str:
            return False
        now = datetime.now().time().replace(second=0, microsecond=0)
        if start_str:
            start_t = self._parse_hhmm(start_str)
            if start_t and now < start_t:
                logger.debug("Fora da janela de horário (antes de %s). Aguardando.", start_str)
                return True
        if end_str:
            end_t = self._parse_hhmm(end_str)
            if end_t and now >= end_t:
                logger.debug("Fora da janela de horário (após %s). Sem novas entradas.", end_str)
                return True
        return False

    def _check_force_close(self) -> None:
        """Fecha forçadamente todas as posições ao atingir o horário configurado."""
        if self.config.force_close_time is None or self._force_closed_today:
            return
        force_t = self._parse_hhmm(self.config.force_close_time)
        if force_t is None:
            return
        now = datetime.now().time()
        if now >= force_t:
            logger.warning(
                "Horário de fechamento forçado atingido (%s). Encerrando posições.",
                self.config.force_close_time,
            )
            for trade in list(self.trades):
                if trade.status == TradeStatus.OPEN:
                    self._force_close_position(trade)
                elif trade.status == TradeStatus.PENDING:
                    self._cancel_order(trade, "fechamento forçado por horário")
            self._force_closed_today = True

    # ------------------------------------------------------------------
    # Comunicação com MT5
    # ------------------------------------------------------------------
    def _connect(self) -> bool:
        if not mt5.initialize():
            logger.error("Falha ao inicializar MT5: %s", mt5.last_error())
            return False
        info = mt5.account_info()
        if info is None:
            logger.error("Conta não encontrada. Verifique o login no MT5.")
            mt5.shutdown()
            return False
        logger.info(
            "Conectado ao MT5 | Conta: %s | Saldo: %.2f %s",
            info.login,
            info.balance,
            info.currency,
        )
        return True

    def _get_symbol_info(self) -> Optional[object]:
        info = mt5.symbol_info(self.config.symbol)
        if info is None:
            logger.error("Símbolo %s não encontrado.", self.config.symbol)
            return None
        if not info.visible:
            mt5.symbol_select(self.config.symbol, True)
        return info

    def _get_bars(self) -> Optional[pd.DataFrame]:
        rates = mt5.copy_rates_from_pos(
            self.config.symbol,
            self._mt5_timeframe,
            0,
            self.config.bars_to_fetch,
        )
        if rates is None or len(rates) == 0:
            logger.warning("Sem dados para %s.", self.config.symbol)
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def _get_current_price(self) -> Optional[tuple[float, float]]:
        """Retorna (bid, ask) do símbolo."""
        tick = mt5.symbol_info_tick(self.config.symbol)
        if tick is None:
            return None
        return tick.bid, tick.ask

    def _point_value(self) -> float:
        info = mt5.symbol_info(self.config.symbol)
        return info.point if info else 1.0

    def _tick_size(self) -> float:
        """Retorna o tick size do símbolo (trade_tick_size).

        É a unidade mínima negociável de preço — usada para converter
        parâmetros de gestão de risco (entry_offset, stop_loss_pts,
        partial_pts, break_even_pts) em unidades de preço.

        Para a maioria dos ativos B3 (WIN, WDO, ações), tick_size == point.
        Para ativos onde diferem (ex.: alguns CFDs), usar tick_size garante
        que offsets e stops tenham tamanho real correto independente de point.

        Fallback: point value → 1.0.
        """
        info = mt5.symbol_info(self.config.symbol)
        if info is None:
            return 1.0
        return info.trade_tick_size or info.point or 1.0

    # ------------------------------------------------------------------
    # Criação de ordem limite
    # ------------------------------------------------------------------
    def _place_limit_order(self, direction: Direction, ref_price: float) -> Optional[Trade]:
        """Cria uma ordem limite com entry_offset a partir do preço de referência.

        Parâmetros:
            direction: Direção da operação (BUY ou SELL).
            ref_price: Preço de referência para calcular a entrada (ex.: MA200, EMA, etc.).

        Quando um symbol_gate está configurado (modo orquestrador), verifica se o
        símbolo está livre antes de enviar a ordem. Se ocupado por outra estratégia,
        retorna None sem enviar nada.
        """
        if self._symbol_gate is not None:
            if not self._symbol_gate.try_acquire_symbol(self.config.symbol):
                logger.info(
                    "Símbolo %s ocupado por outra estratégia. Sinal ignorado.",
                    self.config.symbol,
                )
                return None

        # Busca sym_info antes dos cálculos para usar tick_size
        sym_info = mt5.symbol_info(self.config.symbol)
        if sym_info is None:
            logger.error("symbol_info retornou None para %s", self.config.symbol)
            if self._symbol_gate is not None:
                self._symbol_gate.release_trade(self.config.symbol)
            return None

        point = sym_info.point or 1.0
        digits = sym_info.digits
        tick_size = sym_info.trade_tick_size or point

        # entry_offset e stop_loss_pts são expressos em ticks (trade_tick_size)
        offset = self.config.entry_offset * tick_size
        sl_pts = self.config.stop_loss_pts * tick_size

        if direction == Direction.BUY:
            order_price = ref_price + offset
            stop_loss = order_price - sl_pts
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            order_price = ref_price - offset
            stop_loss = order_price + sl_pts
            order_type = mt5.ORDER_TYPE_SELL_LIMIT

        logger.debug(
            "Símbolo %s | point=%.6f  tick_size=%.6f  digits=%d",
            self.config.symbol, point, tick_size, digits,
        )
        logger.debug(
            "Preços brutos | ref=%.5f  offset=%.5f  order_price=%.5f  stop_loss=%.5f",
            ref_price, offset, order_price, stop_loss,
        )

        # Arredonda ao múltiplo mais próximo do tick_size do símbolo (obrigatório pelo MT5).
        # tick_size é lido do MT5 via sym_info.trade_tick_size — genérico para qualquer ativo:
        #   WINM25 → 5.0  |  WDOM25 → 0.5  |  PETR4 → 0.01  |  EURUSD → 0.00001
        if tick_size > 0:
            order_price = round(round(order_price / tick_size) * tick_size, digits)
            stop_loss = round(round(stop_loss / tick_size) * tick_size, digits)
        else:
            order_price = round(order_price, digits)
            stop_loss = round(stop_loss, digits)

        logger.debug(
            "Preços ajustados ao tick | order_price=%.5f  stop_loss=%.5f",
            order_price, stop_loss,
        )

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.config.symbol,
            "volume": self.config.lot_size,
            "type": order_type,
            "price": order_price,
            "sl": stop_loss,
            "deviation": self.config.slippage,
            "magic": 20250001,
            "comment": f"{self.strategy.__class__.__name__}",
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        logger.debug("Request MT5: %s", request)

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                "Falha ao enviar ordem: %s (retcode=%s) | "
                "order_price=%.5f  stop_loss=%.5f  tick_size=%.6f  ref=%.5f",
                mt5.last_error() if result is None else result.comment,
                result.retcode if result is not None else "N/A",
                order_price, stop_loss, tick_size, ref_price,
            )
            # Libera a reserva adquirida via try_acquire_symbol
            if self._symbol_gate is not None:
                self._symbol_gate.release_trade(self.config.symbol)
            return None

        self._trade_id_counter += 1
        trade = Trade(
            trade_id=self._trade_id_counter,
            symbol=self.config.symbol,
            direction=direction,
            order_price=order_price,
            stop_loss=stop_loss,
            reference_price_at_entry=ref_price,
            lot_size=self.config.lot_size,
            status=TradeStatus.PENDING,
            mt5_ticket=result.order,
        )
        self.trades.append(trade)

        if self._db:
            trade.db_id = self._db.insert_trade(
                symbol=self.config.symbol,
                strategy_name=self._strategy_name,
                direction=direction.value,
                order_price=order_price,
                stop_loss=stop_loss,
                reference_price=ref_price,
                lot_size=self.config.lot_size,
                status="pending",
            )
            if trade.db_id is None:
                logger.warning("Trade pendente não foi persistido no banco: %s", trade)

        self._discord.on_order_placed(
            symbol=self.config.symbol,
            direction=direction.value,
            order_price=order_price,
            stop_loss=stop_loss,
            lot_size=self.config.lot_size,
            strategy_name=self._strategy_name,
        )

        logger.info("Ordem pendente criada: %s (ticket=%d)", trade, result.order)
        return trade

    # ------------------------------------------------------------------
    # Cancelamento de ordem pendente
    # ------------------------------------------------------------------
    def _cancel_order(self, trade: Trade, reason: str = "cancelado") -> None:
        if trade.mt5_ticket is None:
            trade.status = TradeStatus.CANCELLED
            trade.close_reason = reason
            trade.closed_at = datetime.now()
            if self._db and trade.db_id:
                self._db.cancel_trade(
                    trade.db_id,
                    close_reason=reason,
                    closed_at=trade.closed_at,
                )
            return

        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": trade.mt5_ticket,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.warning(
                "Falha ao cancelar ordem %d: %s",
                trade.mt5_ticket,
                mt5.last_error() if result is None else result.comment,
            )
        else:
            logger.info("Ordem %d cancelada: %s", trade.mt5_ticket, reason)

        trade.status = TradeStatus.CANCELLED
        trade.close_reason = reason
        trade.closed_at = datetime.now()

        if self._db and trade.db_id:
            self._db.cancel_trade(
                trade.db_id,
                close_reason=reason,
                closed_at=trade.closed_at,
            )

        if self._symbol_gate is not None:
            self._symbol_gate.release_trade(self.config.symbol)

    # ------------------------------------------------------------------
    # Fechamento parcial
    # ------------------------------------------------------------------
    def _partial_close(self, trade: Trade, pct: float, label: str) -> None:
        if trade.mt5_ticket is None:
            return

        positions = mt5.positions_get(ticket=trade.mt5_ticket)
        if not positions:
            positions = mt5.positions_get(symbol=self.config.symbol)
            positions = [p for p in positions if p.magic == 20250001] if positions else []

        if not positions:
            logger.warning("Posição não encontrada para fechamento parcial (%s).", label)
            return

        pos = positions[0]
        close_volume = round(pos.volume * pct, 2)
        if close_volume < mt5.symbol_info(self.config.symbol).volume_min:
            close_volume = mt5.symbol_info(self.config.symbol).volume_min

        if trade.direction == Direction.BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(self.config.symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.config.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.config.symbol,
            "volume": close_volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": self.config.slippage,
            "magic": 20250001,
            "comment": f"bot_{label}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                "Falha no fechamento parcial %s: %s",
                label,
                mt5.last_error() if result is None else result.comment,
            )
        else:
            logger.info(
                "Fechamento parcial %s realizado: %.2f lotes | Trade#%d",
                label,
                close_volume,
                trade.trade_id,
            )

    # ------------------------------------------------------------------
    # Fechamento forçado (a mercado)
    # ------------------------------------------------------------------
    def _force_close_position(self, trade: Trade) -> None:
        """Fecha a posição aberta a mercado (fechamento forçado por horário)."""
        if trade.mt5_ticket is None:
            return

        positions = mt5.positions_get(ticket=trade.mt5_ticket)
        if not positions:
            return

        pos = positions[0]

        if trade.direction == Direction.BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(self.config.symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(self.config.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.config.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": self.config.slippage,
            "magic": 20250001,
            "comment": "fechamento_forcado",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info("Trade#%d fechado forçadamente.", trade.trade_id)
            self._on_position_closed(trade)
        else:
            logger.error(
                "Falha ao fechar forçadamente Trade#%d: %s",
                trade.trade_id,
                mt5.last_error() if result is None else result.comment,
            )

    # ------------------------------------------------------------------
    # Break-even
    # ------------------------------------------------------------------
    def _apply_break_even(self, trade: Trade) -> None:
        """Move o SL para o preço de entrada quando o lucro atingir break_even_pts."""
        if trade.entry_price is None or trade.mt5_ticket is None:
            return

        positions = mt5.positions_get(ticket=trade.mt5_ticket)
        if not positions:
            return

        pos = positions[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.config.symbol,
            "position": pos.ticket,
            "sl": trade.entry_price,
            "tp": pos.tp,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            trade.break_even_applied = True
            logger.info(
                "Break-even aplicado: Trade#%d SL → %.5f (entry price)",
                trade.trade_id,
                trade.entry_price,
            )
        else:
            logger.warning(
                "Falha ao aplicar break-even Trade#%d: %s",
                trade.trade_id,
                mt5.last_error() if result is None else result.comment,
            )

    # ------------------------------------------------------------------
    # Monitoramento de ordens pendentes
    # ------------------------------------------------------------------
    def _monitor_pending_orders(self) -> None:
        point = self._point_value()
        pending = [t for t in self.trades if t.status == TradeStatus.PENDING]

        for trade in pending:
            # Cancelar após N barras sem preenchimento
            if self.config.cancel_pending_after_bars is not None:
                bars_elapsed = int(
                    (datetime.now() - trade.created_at).total_seconds()
                    / (self.config.timeframe_minutes * 60)
                )
                if bars_elapsed >= self.config.cancel_pending_after_bars:
                    logger.info(
                        "Ordem #%d expirada após %d barras. Cancelando.",
                        trade.trade_id,
                        bars_elapsed,
                    )
                    self._cancel_order(trade, f"expirada após {bars_elapsed} barras")
                    continue

            prices = self._get_current_price()
            if prices is None:
                continue
            bid, ask = prices

            if trade.mt5_ticket:
                positions = mt5.positions_get(symbol=self.config.symbol)
                if positions:
                    activated = [
                        p for p in positions
                        if p.magic == 20250001 and abs(p.price_open - trade.order_price) < point * 2
                    ]
                    if activated:
                        trade.status = TradeStatus.OPEN
                        trade.entry_price = activated[0].price_open
                        trade.mt5_ticket = activated[0].ticket
                        trade.opened_at = datetime.now()
                        logger.info("Ordem ativada: %s @ %.5f", trade, trade.entry_price)

                        if self._db and trade.db_id:
                            self._db.activate_trade(
                                trade.db_id,
                                entry_price=trade.entry_price,
                                opened_at=trade.opened_at,
                            )

                        self._discord.on_trade_activated(
                            symbol=self.config.symbol,
                            direction=trade.direction.value,
                            entry_price=trade.entry_price,
                            strategy_name=self._strategy_name,
                        )
                        continue

            if trade.direction == Direction.BUY:
                if bid <= trade.stop_loss:
                    logger.info(
                        "Preço cruzou o stop antes da ativação. Cancelando: %s", trade
                    )
                    self._cancel_order(trade, "preço cruzou stop antes da ativação")
            else:
                if ask >= trade.stop_loss:
                    logger.info(
                        "Preço cruzou o stop antes da ativação. Cancelando: %s", trade
                    )
                    self._cancel_order(trade, "preço cruzou stop antes da ativação")

    # ------------------------------------------------------------------
    # Monitoramento de posições abertas (parciais, break-even e stop)
    # ------------------------------------------------------------------
    def _monitor_open_positions(self) -> None:
        # Usa tick_size para converter partial_pts e break_even_pts em preço
        tick = self._tick_size()
        open_trades = [t for t in self.trades if t.status == TradeStatus.OPEN]

        for trade in open_trades:
            prices = self._get_current_price()
            if prices is None:
                continue
            bid, ask = prices

            positions = mt5.positions_get(symbol=self.config.symbol)
            active_tickets = {p.ticket for p in positions} if positions else set()

            if trade.mt5_ticket not in active_tickets:
                self._on_position_closed(trade)
                continue

            # Break-even: mover SL para entry quando lucro atingir break_even_pts
            if (
                self.config.break_even_pts is not None
                and not trade.break_even_applied
                and trade.entry_price is not None
            ):
                if trade.direction == Direction.BUY:
                    profit_ticks = (bid - trade.entry_price) / tick
                else:
                    profit_ticks = (trade.entry_price - ask) / tick

                if profit_ticks >= self.config.break_even_pts:
                    self._apply_break_even(trade)

            if not trade.partial1_closed:
                if trade.direction == Direction.BUY:
                    target1 = trade.entry_price + self.config.partial1_pts * tick
                    if bid >= target1:
                        self._partial_close(trade, self.config.partial1_pct, "parcial1")
                        trade.partial1_closed = True
                        if self._db and trade.db_id:
                            self._db.mark_partial1_closed(trade.db_id)
                        self._discord.on_partial_closed(
                            symbol=self.config.symbol,
                            partial_number=1,
                            price=bid,
                            volume=round(trade.lot_size * self.config.partial1_pct, 2),
                            strategy_name=self._strategy_name,
                        )
                else:
                    target1 = trade.entry_price - self.config.partial1_pts * tick
                    if ask <= target1:
                        self._partial_close(trade, self.config.partial1_pct, "parcial1")
                        trade.partial1_closed = True
                        if self._db and trade.db_id:
                            self._db.mark_partial1_closed(trade.db_id)
                        self._discord.on_partial_closed(
                            symbol=self.config.symbol,
                            partial_number=1,
                            price=ask,
                            volume=round(trade.lot_size * self.config.partial1_pct, 2),
                            strategy_name=self._strategy_name,
                        )

            elif not trade.partial2_closed:
                if trade.direction == Direction.BUY:
                    target2 = trade.entry_price + self.config.partial2_pts * tick
                    if bid >= target2:
                        remaining_pct = self.config.partial2_pct / (1 - self.config.partial1_pct)
                        self._partial_close(trade, remaining_pct, "parcial2")
                        trade.partial2_closed = True
                        if self._db and trade.db_id:
                            self._db.mark_partial2_closed(trade.db_id)
                        self._discord.on_partial_closed(
                            symbol=self.config.symbol,
                            partial_number=2,
                            price=bid,
                            volume=round(trade.lot_size * self.config.partial2_pct, 2),
                            strategy_name=self._strategy_name,
                        )
                else:
                    target2 = trade.entry_price - self.config.partial2_pts * tick
                    if ask <= target2:
                        remaining_pct = self.config.partial2_pct / (1 - self.config.partial1_pct)
                        self._partial_close(trade, remaining_pct, "parcial2")
                        trade.partial2_closed = True
                        if self._db and trade.db_id:
                            self._db.mark_partial2_closed(trade.db_id)
                        self._discord.on_partial_closed(
                            symbol=self.config.symbol,
                            partial_number=2,
                            price=ask,
                            volume=round(trade.lot_size * self.config.partial2_pct, 2),
                            strategy_name=self._strategy_name,
                        )

    def _on_position_closed(self, trade: Trade) -> None:
        """Chamado quando uma posição aberta é detectada como fechada."""
        history = mt5.history_deals_get(position=trade.mt5_ticket)
        pnl = 0.0
        close_reason = "desconhecido"

        if history:
            for deal in history:
                pnl += deal.profit
            close_reason = "stop atingido" if pnl < 0 else "alvo atingido"

        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.now()
        trade.profit_loss = pnl
        trade.close_reason = close_reason

        self._daily_pnl += pnl

        if self._db and trade.db_id:
            self._db.close_trade(
                trade.db_id,
                profit_loss=pnl,
                close_reason=close_reason,
                closed_at=trade.closed_at,
            )
        elif self._db:
            logger.warning("Trade fechado sem db_id; painel pode ficar desatualizado: %s", trade)

        if pnl < 0:
            self._daily_stops += 1
            logger.warning(
                "STOP atingido: %s | PnL: %.2f | Stops hoje: %d | PnL do dia: %.2f",
                trade,
                pnl,
                self._daily_stops,
                self._daily_pnl,
            )

        self._discord.on_trade_closed(
            symbol=self.config.symbol,
            direction=trade.direction.value,
            pnl=pnl,
            close_reason=close_reason,
            daily_stops=self._daily_stops,
            strategy_name=self._strategy_name,
        )

        if pnl < 0 and self._daily_stops >= self.config.max_daily_stops:
            logger.warning(
                "BLOQUEIO: %d stops atingidos hoje. Sem novas operações.",
                self._daily_stops,
            )
            self._discord.on_daily_stop_limit(
                symbol=self.config.symbol,
                daily_stops=self._daily_stops,
                max_daily_stops=self.config.max_daily_stops,
                strategy_name=self._strategy_name,
            )
        else:
            logger.info(
                "Posição fechada no alvo: %s | PnL: %.2f | PnL do dia: %.2f",
                trade,
                pnl,
                self._daily_pnl,
            )

        if self._symbol_gate is not None:
            self._symbol_gate.release_trade(self.config.symbol)

    def _sleep(self, seconds: float) -> None:
        """Aguarda `seconds`, podendo ser interrompido antecipadamente pelo stop_event."""
        if self._stop_event is not None:
            self._stop_event.wait(timeout=seconds)
        else:
            time.sleep(seconds)

    def stop(self) -> None:
        self._is_running = False
        if self._stop_event is not None:
            self._stop_event.set()

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("=" * 60)
        logger.info(
            "Iniciando Robô de Trade | Estratégia: %s",
            self.strategy.__class__.__name__,
        )
        logger.info(
            "Símbolo: %s | Lote: %.2f | TF: M%d",
            self.config.symbol,
            self.config.lot_size,
            self.config.timeframe_minutes,
        )
        logger.info("=" * 60)

        if not self._skip_connect:
            if not self._connect():
                logger.error("Não foi possível conectar ao MT5. Encerrando.")
                return

        sym_info = self._get_symbol_info()
        if sym_info is None:
            if not self._skip_connect:
                mt5.shutdown()
            return

        self._is_running = True
        last_signal_bar: Optional[int] = None

        if self._db:
            self._db.upsert_status(is_running=True, daily_stops=self._daily_stops)

        self._discord.on_bot_started(
            symbol=self.config.symbol,
            strategy_name=self._strategy_name,
            lot_size=self.config.lot_size,
            timeframe_minutes=self.config.timeframe_minutes,
        )

        try:
            while self._is_running and not (
                self._stop_event is not None and self._stop_event.is_set()
            ):
                self._reset_daily_stats_if_needed()
                self._check_force_close()

                self._monitor_pending_orders()
                self._monitor_open_positions()

                current_price: Optional[float] = None
                prices = self._get_current_price()
                if prices:
                    current_price = prices[0]

                if self._is_blocked():
                    reason = (
                        f"{self._daily_stops} stops no dia"
                        if self._daily_stops >= self.config.max_daily_stops
                        else f"PnL do dia: {self._daily_pnl:.2f}"
                        if (
                            self.config.max_daily_loss_pts is not None
                            and self._daily_pnl <= -self.config.max_daily_loss_pts
                        )
                        else f"meta de lucro atingida ({self._daily_pnl:.2f})"
                        if (
                            self.config.max_daily_profit_pts is not None
                            and self._daily_pnl >= self.config.max_daily_profit_pts
                        )
                        else f"{self._open_trades_count()} operações abertas"
                    )
                    logger.debug("Bloqueado (%s). Aguardando...", reason)
                    if self._db:
                        self._db.upsert_status(
                            is_running=True,
                            daily_stops=self._daily_stops,
                            current_price=current_price,
                            block_reason=reason,
                        )
                    self._sleep(self.config.loop_interval)
                    continue

                if self._is_outside_trading_window():
                    if self._db:
                        self._db.upsert_status(
                            is_running=True,
                            daily_stops=self._daily_stops,
                            current_price=current_price,
                            block_reason="fora da janela de horário",
                        )
                    self._sleep(self.config.loop_interval)
                    continue

                df = self._get_bars()
                if df is None or len(df) < 10:
                    if self._db:
                        self._db.upsert_status(
                            is_running=True,
                            daily_stops=self._daily_stops,
                            current_price=current_price,
                        )
                    self._sleep(self.config.loop_interval)
                    continue

                current_bar_time = int(df.iloc[-1]["time"].timestamp())

                closed_df = df.iloc[:-1]

                # Quando rejection_candles=0 a estratégia detecta toque no
                # candle ainda em formação — passamos o df completo (com o
                # candle vivo). Para rejection_candles>=1 o comportamento
                # original é mantido (apenas barras fechadas).
                use_live_bar = getattr(self.strategy_config, "rejection_candles", 1) == 0
                signal_df = df if use_live_bar else closed_df

                if use_live_bar:
                    logger.debug(
                        "Modo candle vivo ativo (rejection_candles=0) — "
                        "detectando sinal no candle em andamento."
                    )

                # Passa tick_size como point_value para as estratégias
                # (touch_threshold_pts e similares são calculados em ticks)
                tick_val = self._tick_size()
                signal = self.strategy.detect_signal(
                    signal_df, self.strategy_config, point_value=tick_val
                )

                ref_price_for_status: Optional[float] = None
                last_signal_at: Optional[datetime] = None

                if signal is not None:
                    if last_signal_bar != current_bar_time:
                        last_signal_bar = current_bar_time
                        last_signal_at = datetime.now()

                        ref_price_for_status = self.strategy.get_reference_price(
                            signal_df, self.strategy_config, point_value=tick_val
                        )

                        logger.info(
                            "Novo sinal: %s | Preço de referência=%.5f",
                            signal.value,
                            ref_price_for_status,
                        )
                        trade = self._place_limit_order(signal, ref_price_for_status)
                        if trade:
                            logger.info("Nova ordem criada: %s", trade)

                if self._db:
                    self._db.upsert_status(
                        is_running=True,
                        daily_stops=self._daily_stops,
                        current_price=current_price,
                        current_ma200=ref_price_for_status,
                        last_signal_at=last_signal_at,
                        block_reason=None,
                    )

                self._sleep(self.config.loop_interval)

        except KeyboardInterrupt:
            logger.info("Robô interrompido pelo usuário.")
            self.stop()
        finally:
            self._is_running = False
            self._discord.on_bot_stopped(
                symbol=self.config.symbol,
                strategy_name=self._strategy_name,
                daily_pnl=self._daily_pnl,
            )
            if self._db:
                self._db.upsert_status(
                    is_running=False,
                    daily_stops=self._daily_stops,
                    block_reason="robô encerrado",
                )
                self._db.close()
            if not self._skip_connect:
                mt5.shutdown()
                logger.info("Conexão MT5 encerrada.")
            self._print_summary()

    # ------------------------------------------------------------------
    # Resumo final
    # ------------------------------------------------------------------
    def _print_summary(self) -> None:
        closed = [t for t in self.trades if t.status == TradeStatus.CLOSED]
        wins = [t for t in closed if (t.profit_loss or 0) > 0]
        losses = [t for t in closed if (t.profit_loss or 0) <= 0]
        total_pnl = sum(t.profit_loss or 0 for t in closed)
        win_rate = len(wins) / len(closed) * 100 if closed else 0.0

        logger.info("=" * 60)
        logger.info("RESUMO DA SESSÃO")
        logger.info("  Total de operações: %d", len(self.trades))
        logger.info(
            "  Fechadas: %d | Wins: %d | Losses: %d",
            len(closed),
            len(wins),
            len(losses),
        )
        logger.info("  Win Rate: %.1f%%", win_rate)
        logger.info("  PnL Total: %.2f", total_pnl)
        logger.info("  Stops no último dia: %d", self._daily_stops)
        logger.info("=" * 60)
