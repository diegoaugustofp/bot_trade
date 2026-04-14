"""
Modelos compartilhados do Trade Bot MT5
=======================================

Este módulo contém as enumerações e dataclasses usadas em todo o pacote:
- Direction: direção da operação (BUY/SELL)
- TradeStatus: estado atual de uma operação
- Trade: representação de uma operação individual
- BotConfig: configuração geral do robô (execução e gestão de risco)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


@dataclass
class Trade:
    trade_id: int
    symbol: str
    direction: Direction
    order_price: float
    stop_loss: float
    reference_price_at_entry: float
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
    db_id: Optional[int] = None
    break_even_applied: bool = False

    def __str__(self) -> str:
        return (
            f"Trade#{self.trade_id} {self.direction.value} {self.symbol} "
            f"@ {self.order_price} SL={self.stop_loss} | {self.status.value}"
        )


@dataclass
class BotConfig:
    """Configuração geral do robô: símbolo, lote, gestão de risco e parciais.

    Os parâmetros específicos de cada estratégia ficam nos respectivos dataclasses
    em trade_bot/strategies/.

    Parâmetros obrigatórios:
        symbol: Símbolo a operar (ex: 'WINM25').
        lot_size: Tamanho da posição em lotes/contratos.
        entry_offset: Distância em ticks (trade_tick_size) da referência para entrada.
        stop_loss_pts: Stop loss em ticks (trade_tick_size).
        timeframe_minutes: Timeframe em minutos (1, 5, 15, 30, 60).
        partial1_pct: Percentual da posição a fechar na 1ª parcial.
        partial1_pts: Alvo da 1ª parcial em ticks de lucro.
        partial2_pct: Percentual da posição a fechar na 2ª parcial.
        partial2_pts: Alvo da 2ª parcial em ticks de lucro.
        partial3_pts: Alvo do restante em ticks de lucro.
        max_open_trades: Máximo de operações abertas simultaneamente.
        max_daily_stops: Após este número de stops no dia, bloqueia novas entradas.
        loop_interval: Intervalo do loop principal em segundos.
        slippage: Desvio máximo permitido ao executar ordens (pontos).
        bars_to_fetch: Número de barras históricas a buscar.

    Parâmetros opcionais — janela de horário (None = sem restrição):
        trading_start_time: Horário mínimo para abrir posições, formato "HH:MM".
        trading_end_time: Horário máximo para abrir novas posições, formato "HH:MM".
        force_close_time: Horário para fechar forçadamente todas as posições, "HH:MM".

    Parâmetros opcionais — gestão de risco (None = desativado):
        max_daily_loss_pts: Para de abrir posições ao acumular este prejuízo no dia.
        max_daily_profit_pts: Para de abrir posições ao atingir esta meta de lucro no dia.
        break_even_pts: Move o stop para o entry price quando a posição atingir N ticks de lucro.
        cancel_pending_after_bars: Cancela ordens pendentes após N barras sem preenchimento.
    """
    symbol: str = "WINM25"
    lot_size: float = 1.0
    entry_offset: float = 10.0
    stop_loss_pts: float = 20.0
    timeframe_minutes: int = 5

    partial1_pct: float = 0.60
    partial1_pts: float = 20.0
    partial2_pct: float = 0.20
    partial2_pts: float = 50.0
    partial3_pts: float = 100.0

    max_open_trades: int = 3
    max_daily_stops: int = 2

    loop_interval: float = 10.0
    slippage: int = 5
    bars_to_fetch: int = 300

    trading_start_time: Optional[str] = None
    trading_end_time: Optional[str] = None
    force_close_time: Optional[str] = None

    max_daily_loss_pts: Optional[float] = None
    max_daily_profit_pts: Optional[float] = None
    break_even_pts: Optional[float] = None
    cancel_pending_after_bars: Optional[int] = None
