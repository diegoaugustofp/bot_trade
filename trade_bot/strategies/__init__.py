"""
Estratégias disponíveis para o Trade Bot MT5
=============================================

Cada estratégia é uma classe que herda de BaseStrategy e implementa:
- detect_signal(df, config) -> Optional[Direction]
- get_reference_price(df, config) -> float

Estratégias disponíveis:
    MA200RejectionStrategy  — Recusa na MA200 (estratégia original)
    EMACrossoverStrategy    — Cruzamento de EMAs rápida/lenta
    PullbackTrendStrategy   — Pullback em tendência via EMA34
    RSIDivergenceStrategy   — Divergência de RSI
    BreakoutNBarsStrategy   — Rompimento de N barras
    MACDSignalStrategy      — Cruzamento da linha MACD com a linha de sinal
    POIStrategy             — Recusa em Pontos de Interesse definidos pelo usuário
"""

from trade_bot.strategies.base import BaseStrategy
from trade_bot.strategies.ma200_rejection import MA200RejectionStrategy, MA200Config
from trade_bot.strategies.ema_crossover import EMACrossoverStrategy, EMACrossoverConfig
from trade_bot.strategies.pullback_trend import PullbackTrendStrategy, PullbackTrendConfig
from trade_bot.strategies.rsi_divergence import RSIDivergenceStrategy, RSIDivergenceConfig
from trade_bot.strategies.breakout_nbars import BreakoutNBarsStrategy, BreakoutNBarsConfig
from trade_bot.strategies.macd_signal import MACDSignalStrategy, MACDSignalConfig
from trade_bot.strategies.poi import POIStrategy, POIConfig

__all__ = [
    "BaseStrategy",
    "MA200RejectionStrategy",
    "MA200Config",
    "EMACrossoverStrategy",
    "EMACrossoverConfig",
    "PullbackTrendStrategy",
    "PullbackTrendConfig",
    "RSIDivergenceStrategy",
    "RSIDivergenceConfig",
    "BreakoutNBarsStrategy",
    "BreakoutNBarsConfig",
    "MACDSignalStrategy",
    "MACDSignalConfig",
    "POIStrategy",
    "POIConfig",
]
