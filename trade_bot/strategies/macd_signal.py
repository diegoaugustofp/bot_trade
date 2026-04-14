"""
Estratégia: Cruzamento MACD/Signal
=====================================

Lógica:
    Calcula o MACD (Moving Average Convergence Divergence) e sua linha de sinal,
    gerando entradas quando as linhas se cruzam com confirmação de histograma:

    - COMPRA: A linha MACD cruza a linha de sinal de BAIXO para CIMA e o
      histograma (MACD - Signal) passa de negativo para positivo.

    - VENDA:  A linha MACD cruza a linha de sinal de CIMA para BAIXO e o
      histograma passa de positivo para negativo.

    O cruzamento é detectado comparando a relação MACD vs Signal na última barra
    fechada com a relação na barra anterior.

Parâmetros (MACDSignalConfig):
    fast_period (int): Período da EMA rápida do MACD. Padrão: 12.
    slow_period (int): Período da EMA lenta do MACD. Padrão: 26.
    signal_period (int): Período da EMA da linha de sinal. Padrão: 9.

Exemplo de uso:
    from trade_bot.strategies.macd_signal import MACDSignalStrategy, MACDSignalConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=MACDSignalStrategy(),
        strategy_config=MACDSignalConfig(fast_period=12, slow_period=26, signal_period=9),
    )
    engine.run()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_bot.models import Direction
from trade_bot.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class MACDSignalConfig:
    """Parâmetros da estratégia de cruzamento MACD/Signal.

    Atributos:
        fast_period: Período da EMA rápida. Padrão: 12.
        slow_period: Período da EMA lenta. Padrão: 26.
        signal_period: Período da EMA da linha de sinal. Padrão: 9.
    """
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9


def _calculate_macd(
    closes: pd.Series,
    fast: int,
    slow: int,
    signal: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calcula MACD, linha de sinal e histograma.

    Retorno:
        Tupla (macd_line, signal_line, histogram).
    """
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


class MACDSignalStrategy(BaseStrategy):
    """Detecta sinal de entrada com base no cruzamento MACD/Signal."""

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: MACDSignalConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme cruzamento MACD detectado.

        Parâmetros:
            df: DataFrame OHLCV com barras fechadas.
            config: Instância de MACDSignalConfig.
            point_value: Não utilizado nesta estratégia (mantido por interface).

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        min_bars = config.slow_period + config.signal_period + 2
        if len(df) < min_bars:
            return None

        macd_line, signal_line, histogram = _calculate_macd(
            df["close"],
            config.fast_period,
            config.slow_period,
            config.signal_period,
        )

        if histogram.isna().iloc[-1] or histogram.isna().iloc[-2]:
            return None

        hist_now = histogram.iloc[-1]
        hist_prev = histogram.iloc[-2]

        macd_now = macd_line.iloc[-1]
        sig_now = signal_line.iloc[-1]
        macd_prev = macd_line.iloc[-2]
        sig_prev = signal_line.iloc[-2]

        bullish_cross = (macd_now > sig_now) and (macd_prev <= sig_prev)
        bearish_cross = (macd_now < sig_now) and (macd_prev >= sig_prev)

        histogram_confirms_buy = hist_now > 0 and hist_prev <= 0
        histogram_confirms_sell = hist_now < 0 and hist_prev >= 0

        if bullish_cross and histogram_confirms_buy:
            logger.info(
                "Sinal de COMPRA detectado (MACD cruzou Signal para cima | hist=%.5f).",
                hist_now,
            )
            return Direction.BUY

        if bearish_cross and histogram_confirms_sell:
            logger.info(
                "Sinal de VENDA detectado (MACD cruzou Signal para baixo | hist=%.5f).",
                hist_now,
            )
            return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: MACDSignalConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o fechamento da última barra como referência de entrada."""
        return float(df["close"].iloc[-1])
