"""
Robô de Trade para MetaTrader 5 - Estratégia de Recusa da MA200
===============================================================

Estratégia:
- Timeframe: M5 (5 minutos)
- Indicador: Média Móvel de 200 períodos
- Sinal: Quando o preço toca a MA200 e recusa (por cima ou por baixo)
- Entrada: 10 pontos acima (compra) ou abaixo (venda) da MA200 na recusa
- Stop: 20 pontos
- Alvos parciais:
  * 1ª parcial: 60% da posição com 20 pontos de lucro
  * 2ª parcial: 20% da posição com 50 pontos de lucro
  * 3ª parcial: 20% restante com 100 pontos de lucro
- Cancelamento: Se o preço passar o stop antes da ativação, cancela a ordem
- Gestão de risco:
  * Máximo de 3 operações simultâneas
  * Após 2 stops no dia, não abre novas posições

Requisitos:
- MetaTrader 5 instalado
- Python: pip install MetaTrader5 pandas numpy

Uso:
    python trade_bot_mt5.py
"""

from __future__ import annotations

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

# ---------------------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trade_bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerações
# ---------------------------------------------------------------------------
class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Configuração do Robô (parametrizável)
# ---------------------------------------------------------------------------
@dataclass
class BotConfig:
    # Símbolo a operar
    symbol: str = "WINM25"

    # Tamanho da posição (em lotes/contratos)
    lot_size: float = 1.0

    # Parâmetros da estratégia
    ma_period: int = 200          # Período da média móvel
    entry_offset: float = 10.0    # Pontos de distância para entrada a partir da MA200
    stop_loss_pts: float = 20.0   # Stop loss em pontos
    timeframe_minutes: int = 5    # Timeframe em minutos

    # Alvos parciais (em pontos)
    partial1_pct: float = 0.60    # 60% da posição
    partial1_pts: float = 20.0    # Alvo da 1ª parcial
    partial2_pct: float = 0.20    # 20% da posição
    partial2_pts: float = 50.0    # Alvo da 2ª parcial
    partial3_pts: float = 100.0   # Alvo do restante (20%)

    # Gestão de risco
    max_open_trades: int = 3      # Máximo de operações abertas simultaneamente
    max_daily_stops: int = 2      # Máximo de stops por dia antes de bloquear

    # Parâmetros de verificação de recusa (candles consecutivos longe da MA)
    touch_threshold_pts: float = 5.0    # Distância máxima para considerar "toque" na MA
    rejection_candles: int = 2          # Número de candles para confirmar recusa

    # Intervalo do loop principal (segundos)
    loop_interval: float = 10.0

    # Desvio máximo permitido ao executar ordens a mercado (pontos)
    slippage: int = 5

    # Número de barras históricas para calcular a MA
    bars_to_fetch: int = 300


# ---------------------------------------------------------------------------
# Representação de uma operação
# ---------------------------------------------------------------------------
@dataclass
class Trade:
    trade_id: int
    symbol: str
    direction: Direction
    order_price: float          # Preço da ordem limite (10 pts da MA)
    stop_loss: float            # Preço do stop loss
    ma200_at_entry: float       # Valor da MA200 quando o sinal foi gerado
    lot_size: float
    status: TradeStatus = TradeStatus.PENDING
    entry_price: Optional[float] = None
    mt5_ticket: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    partial1_closed: bool = False
    partial2_closed: bool = False
    profit_loss: Optional[float] = None
    close_reason: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"Trade#{self.trade_id} {self.direction.value} {self.symbol} "
            f"@ {self.order_price} SL={self.stop_loss} | {self.status.value}"
        )


# ---------------------------------------------------------------------------
# Núcleo do Robô
# ---------------------------------------------------------------------------
class TradeBotMT5:
    def __init__(self, config: BotConfig):
        self.config = config
        self.trades: list[Trade] = []
        self._trade_id_counter: int = 0
        self._daily_stops: int = 0
        self._last_reset_date: date = date.today()
        self._is_running: bool = False

        # Resolve o timeframe do MT5
        tf_map = {
            1: mt5.TIMEFRAME_M1,
            5: mt5.TIMEFRAME_M5,
            15: mt5.TIMEFRAME_M15,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1,
        }
        self._mt5_timeframe = tf_map.get(config.timeframe_minutes, mt5.TIMEFRAME_M5)

    # ------------------------------------------------------------------
    # Gestão de risco
    # ------------------------------------------------------------------
    def _reset_daily_stats_if_needed(self) -> None:
        today = date.today()
        if today != self._last_reset_date:
            logger.info("Novo dia: resetando contadores diários.")
            self._daily_stops = 0
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
        return False

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

    # ------------------------------------------------------------------
    # Cálculo da MA200
    # ------------------------------------------------------------------
    def _calculate_ma200(self, df: pd.DataFrame) -> float:
        """Calcula a MA200 do fechamento. Retorna o valor da MA na última barra fechada."""
        closes = df["close"].values
        if len(closes) < self.config.ma_period:
            raise ValueError("Dados insuficientes para calcular a MA200.")
        ma = np.mean(closes[-self.config.ma_period:])
        return float(ma)

    # ------------------------------------------------------------------
    # Detecção de sinal de recusa
    # ------------------------------------------------------------------
    def _detect_rejection(self, df: pd.DataFrame) -> Optional[Direction]:
        """
        Detecta recusa na MA200.

        Critério:
        - O preço (mínimo ou máximo de um candle) toca a MA200 dentro do threshold.
        - Nos candles seguintes, o preço se afasta da MA, configurando a recusa.
        - Compra: preço vinha caindo, tocou a MA por baixo, e recusou para cima.
        - Venda: preço vinha subindo, tocou a MA por cima, e recusou para baixo.
        """
        point = self._point_value()
        threshold = self.config.touch_threshold_pts * point
        rej_candles = self.config.rejection_candles

        # Precisamos de pelo menos ma_period + rej_candles + 1 barras
        if len(df) < self.config.ma_period + rej_candles + 2:
            return None

        # Calcula a MA em cada ponto (rolling mean)
        df = df.copy()
        df["ma200"] = df["close"].rolling(self.config.ma_period).mean()

        # Descarta barras sem MA calculada e pega as últimas N+1 com MA
        valid = df.dropna(subset=["ma200"]).reset_index(drop=True)

        if len(valid) < rej_candles + 2:
            return None

        # Barra de "toque" é a barra logo antes das barras de confirmação
        # Index: touch_idx = -(rej_candles+1), confirmation: -rej_candles ... -1
        touch_idx = -(rej_candles + 1)
        touch_bar = valid.iloc[touch_idx]
        ma_touch = touch_bar["ma200"]

        # Verifica toque: low ou high dentro do threshold da MA
        touched_from_below = touch_bar["low"] <= ma_touch + threshold
        touched_from_above = touch_bar["high"] >= ma_touch - threshold

        if not (touched_from_below or touched_from_above):
            return None

        # Barras de confirmação (as mais recentes)
        conf_bars = valid.iloc[-rej_candles:]

        # Recusa de alta (compra): toque por baixo, depois fechamentos acima da MA
        if touched_from_below:
            # Todos os candles de confirmação fecham acima da MA
            all_above = all(
                conf_bars.iloc[i]["close"] > valid.iloc[touch_idx + 1 + i]["ma200"]
                for i in range(rej_candles)
            )
            if all_above:
                logger.info("Sinal de COMPRA detectado (recusa na MA200 por baixo).")
                return Direction.BUY

        # Recusa de baixa (venda): toque por cima, depois fechamentos abaixo da MA
        if touched_from_above:
            all_below = all(
                conf_bars.iloc[i]["close"] < valid.iloc[touch_idx + 1 + i]["ma200"]
                for i in range(rej_candles)
            )
            if all_below:
                logger.info("Sinal de VENDA detectado (recusa na MA200 por cima).")
                return Direction.SELL

        return None

    # ------------------------------------------------------------------
    # Criação de ordem limite
    # ------------------------------------------------------------------
    def _place_limit_order(self, direction: Direction, ma200: float) -> Optional[Trade]:
        point = self._point_value()
        offset = self.config.entry_offset * point
        sl_pts = self.config.stop_loss_pts * point

        if direction == Direction.BUY:
            order_price = ma200 + offset
            stop_loss = order_price - sl_pts
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            order_price = ma200 - offset
            stop_loss = order_price + sl_pts
            order_type = mt5.ORDER_TYPE_SELL_LIMIT

        sym_info = mt5.symbol_info(self.config.symbol)
        if sym_info is None:
            return None

        # Arredonda para a precisão do símbolo
        digits = sym_info.digits
        order_price = round(order_price, digits)
        stop_loss = round(stop_loss, digits)

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.config.symbol,
            "volume": self.config.lot_size,
            "type": order_type,
            "price": order_price,
            "sl": stop_loss,
            "deviation": self.config.slippage,
            "magic": 20250001,
            "comment": "MA200_rejection_bot",
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                "Falha ao enviar ordem: %s",
                mt5.last_error() if result is None else result.comment,
            )
            return None

        self._trade_id_counter += 1
        trade = Trade(
            trade_id=self._trade_id_counter,
            symbol=self.config.symbol,
            direction=direction,
            order_price=order_price,
            stop_loss=stop_loss,
            ma200_at_entry=ma200,
            lot_size=self.config.lot_size,
            status=TradeStatus.PENDING,
            mt5_ticket=result.order,
        )
        self.trades.append(trade)
        logger.info("Ordem pendente criada: %s (ticket=%d)", trade, result.order)
        return trade

    # ------------------------------------------------------------------
    # Cancelamento de ordem pendente
    # ------------------------------------------------------------------
    def _cancel_order(self, trade: Trade, reason: str = "cancelado") -> None:
        if trade.mt5_ticket is None:
            trade.status = TradeStatus.CANCELLED
            trade.close_reason = reason
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

    # ------------------------------------------------------------------
    # Fechamento parcial
    # ------------------------------------------------------------------
    def _partial_close(self, trade: Trade, pct: float, label: str) -> None:
        if trade.mt5_ticket is None:
            return

        # Obtém a posição atual
        positions = mt5.positions_get(ticket=trade.mt5_ticket)
        if not positions:
            # Tenta pelo símbolo e magic
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
            "comment": f"MA200_bot_{label}",
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
    # Monitoramento de ordens pendentes
    # ------------------------------------------------------------------
    def _monitor_pending_orders(self) -> None:
        point = self._point_value()
        pending = [t for t in self.trades if t.status == TradeStatus.PENDING]

        for trade in pending:
            prices = self._get_current_price()
            if prices is None:
                continue
            bid, ask = prices

            # Verifica se a ordem foi ativada (agora é uma posição)
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
                        continue

            # Verifica se o preço cruzou o stop antes da ativação → cancela
            if trade.direction == Direction.BUY:
                # Para compra, cancelar se o preço cair abaixo do stop
                if bid <= trade.stop_loss:
                    logger.info(
                        "Preço cruzou o stop antes da ativação. Cancelando: %s", trade
                    )
                    self._cancel_order(trade, "preço cruzou stop antes da ativação")
            else:
                # Para venda, cancelar se o preço subir acima do stop
                if ask >= trade.stop_loss:
                    logger.info(
                        "Preço cruzou o stop antes da ativação. Cancelando: %s", trade
                    )
                    self._cancel_order(trade, "preço cruzou stop antes da ativação")

    # ------------------------------------------------------------------
    # Monitoramento de posições abertas (parciais e stop)
    # ------------------------------------------------------------------
    def _monitor_open_positions(self) -> None:
        point = self._point_value()
        open_trades = [t for t in self.trades if t.status == TradeStatus.OPEN]

        for trade in open_trades:
            prices = self._get_current_price()
            if prices is None:
                continue
            bid, ask = prices

            # Verifica se a posição ainda existe
            positions = mt5.positions_get(symbol=self.config.symbol)
            active_tickets = {p.ticket for p in positions} if positions else set()

            if trade.mt5_ticket not in active_tickets:
                # Posição foi fechada (stop ou target final atingido)
                self._on_position_closed(trade)
                continue

            # Preço atual para fins de cálculo
            current_price = bid if trade.direction == Direction.BUY else ask

            # --- 1ª parcial (60% com 20 pts) ---
            if not trade.partial1_closed:
                if trade.direction == Direction.BUY:
                    target1 = trade.entry_price + self.config.partial1_pts * point
                    if bid >= target1:
                        self._partial_close(trade, self.config.partial1_pct, "parcial1")
                        trade.partial1_closed = True
                else:
                    target1 = trade.entry_price - self.config.partial1_pts * point
                    if ask <= target1:
                        self._partial_close(trade, self.config.partial1_pct, "parcial1")
                        trade.partial1_closed = True

            # --- 2ª parcial (20% com 50 pts) ---
            elif not trade.partial2_closed:
                if trade.direction == Direction.BUY:
                    target2 = trade.entry_price + self.config.partial2_pts * point
                    if bid >= target2:
                        # 20% da posição original = 33% do restante após 1ª parcial
                        remaining_pct = self.config.partial2_pct / (1 - self.config.partial1_pct)
                        self._partial_close(trade, remaining_pct, "parcial2")
                        trade.partial2_closed = True
                else:
                    target2 = trade.entry_price - self.config.partial2_pts * point
                    if ask <= target2:
                        remaining_pct = self.config.partial2_pct / (1 - self.config.partial1_pct)
                        self._partial_close(trade, remaining_pct, "parcial2")
                        trade.partial2_closed = True

            # Nota: o 3º alvo (100 pts) é gerenciado pelo próprio TP na ordem.
            # Se quiser definir TP na abertura, adicionar ao request com:
            # "tp": order_price + 100*point (compra) ou order_price - 100*point (venda)

    def _on_position_closed(self, trade: Trade) -> None:
        """Chamado quando uma posição aberta é detectada como fechada."""
        # Busca histórico de ordens para verificar se foi stop ou target
        history = mt5.history_deals_get(position=trade.mt5_ticket)
        pnl = 0.0
        close_reason = "desconhecido"

        if history:
            for deal in history:
                pnl += deal.profit
            # Simplificação: se PnL negativo, foi stop
            close_reason = "stop atingido" if pnl < 0 else "alvo atingido"

        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.now()
        trade.profit_loss = pnl
        trade.close_reason = close_reason

        if pnl < 0:
            self._daily_stops += 1
            logger.warning(
                "STOP atingido: %s | PnL: %.2f | Stops hoje: %d",
                trade,
                pnl,
                self._daily_stops,
            )
            if self._daily_stops >= self.config.max_daily_stops:
                logger.warning(
                    "BLOQUEIO: %d stops atingidos hoje. Sem novas operações.",
                    self._daily_stops,
                )
        else:
            logger.info(
                "Posição fechada no alvo: %s | PnL: %.2f", trade, pnl
            )

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("=" * 60)
        logger.info("Iniciando Robô de Trade - Recusa MA200")
        logger.info("Símbolo: %s | Lote: %.2f | TF: M%d",
                    self.config.symbol, self.config.lot_size, self.config.timeframe_minutes)
        logger.info("=" * 60)

        if not self._connect():
            logger.error("Não foi possível conectar ao MT5. Encerrando.")
            return

        sym_info = self._get_symbol_info()
        if sym_info is None:
            mt5.shutdown()
            return

        self._is_running = True
        last_signal_bar: Optional[int] = None  # Índice do último candle com sinal gerado

        try:
            while self._is_running:
                self._reset_daily_stats_if_needed()

                # Monitora ordens pendentes e posições abertas
                self._monitor_pending_orders()
                self._monitor_open_positions()

                # Se bloqueado, aguarda
                if self._is_blocked():
                    reason = (
                        f"{self._daily_stops} stops no dia"
                        if self._daily_stops >= self.config.max_daily_stops
                        else f"{self._open_trades_count()} operações abertas"
                    )
                    logger.debug("Bloqueado (%s). Aguardando...", reason)
                    time.sleep(self.config.loop_interval)
                    continue

                # Obtém dados históricos
                df = self._get_bars()
                if df is None or len(df) < self.config.ma_period + 5:
                    time.sleep(self.config.loop_interval)
                    continue

                # Identifica a barra atual (a última barra pode estar incompleta)
                # Usa a penúltima para verificar sinais (barra fechada)
                current_bar_time = int(df.iloc[-1]["time"].timestamp())

                # Calcula MA200 na última barra fechada
                ma200 = self._calculate_ma200(df.iloc[:-1])

                # Detecta sinal de recusa
                direction = self._detect_rejection(df.iloc[:-1])

                if direction is not None:
                    # Evita criar múltiplas ordens no mesmo candle
                    if last_signal_bar != current_bar_time:
                        last_signal_bar = current_bar_time
                        logger.info(
                            "Novo sinal: %s | MA200=%.5f", direction.value, ma200
                        )
                        trade = self._place_limit_order(direction, ma200)
                        if trade:
                            logger.info("Nova ordem criada: %s", trade)

                time.sleep(self.config.loop_interval)

        except KeyboardInterrupt:
            logger.info("Robô interrompido pelo usuário.")
        finally:
            self._is_running = False
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
        logger.info("  Fechadas: %d | Wins: %d | Losses: %d", len(closed), len(wins), len(losses))
        logger.info("  Win Rate: %.1f%%", win_rate)
        logger.info("  PnL Total: %.2f", total_pnl)
        logger.info("  Stops no último dia: %d", self._daily_stops)
        logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    config = BotConfig(
        symbol="WINM25",        # Altere para o símbolo desejado
        lot_size=1.0,           # Tamanho da posição
        ma_period=200,          # Período da média (não altere)
        entry_offset=10.0,      # Pontos da MA para entrada
        stop_loss_pts=20.0,     # Stop em pontos
        partial1_pct=0.60,      # 60% na 1ª parcial
        partial1_pts=20.0,      # Alvo da 1ª parcial em pontos
        partial2_pct=0.20,      # 20% na 2ª parcial
        partial2_pts=50.0,      # Alvo da 2ª parcial em pontos
        partial3_pts=100.0,     # Alvo final em pontos
        max_open_trades=3,      # Máximo simultâneo
        max_daily_stops=2,      # Bloqueia após 2 stops
        timeframe_minutes=5,    # M5
        loop_interval=10.0,     # Verificação a cada 10 segundos
    )

    bot = TradeBotMT5(config)
    bot.run()
