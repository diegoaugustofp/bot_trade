"""
Estratégia: Rompimento de N Barras
=====================================

Lógica:
    Monitora a máxima e a mínima das últimas N barras para detectar rompimentos:

    - COMPRA: O close da última barra supera a máxima das últimas N barras.
    - VENDA:  O close da última barra cai abaixo da mínima das últimas N barras.

    O parâmetro min_range_pts funciona como filtro: se o range (máxima - mínima)
    das últimas N barras for menor que min_range_pts * point_value, o sinal é
    ignorado. Isso evita entradas em mercados laterais sem volatilidade real.

Parâmetros (BreakoutNBarsConfig):
    lookback_bars (int): Número de barras para calcular máxima/mínima do canal. Padrão: 20.
    min_range_pts (float): Range mínimo do canal em pontos do símbolo para
        considerar o sinal. Convertido para unidades de preço multiplicando por
        point_value. Use 0.0 para desativar o filtro. Padrão: 50.0.

Exemplo de uso:
    from trade_bot.strategies.breakout_nbars import BreakoutNBarsStrategy, BreakoutNBarsConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=BreakoutNBarsStrategy(),
        strategy_config=BreakoutNBarsConfig(lookback_bars=20, min_range_pts=50.0),
    )
    engine.run()
"""

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trade_bot.models import Direction
from trade_bot.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class BreakoutNBarsConfig:
    """Parâmetros da estratégia de rompimento de N barras.

    Atributos:
        lookback_bars: Número de barras para calcular máxima/mínima do canal.
            A barra atual (de sinal) não é incluída neste cálculo. Padrão: 20.
        min_range_pts: Range mínimo do canal (máxima - mínima) em pontos do
            símbolo para validar o rompimento. Valores menores são ignorados
            como mercado lateral. Convertido para unidades de preço multiplicando
            por point_value. Use 0.0 para desativar o filtro. Padrão: 50.0.
    """
    lookback_bars: int = 20
    min_range_pts: float = 50.0


class BreakoutNBarsStrategy(BaseStrategy):
    """Detecta rompimento do canal formado pelas últimas N barras."""

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: BreakoutNBarsConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme rompimento detectado.

        Parâmetros:
            df: DataFrame OHLCV com barras fechadas.
            config: Instância de BreakoutNBarsConfig.
            point_value: Valor de um ponto do símbolo em unidades de preço.
                Usado para converter min_range_pts em unidades de preço.

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        if len(df) < config.lookback_bars + 1:
            return None

        channel_bars = df.iloc[-(config.lookback_bars + 1):-1]
        signal_bar = df.iloc[-1]

        channel_high = channel_bars["high"].max()
        channel_low = channel_bars["low"].min()
        channel_range = channel_high - channel_low
        min_range = config.min_range_pts * point_value

        if config.min_range_pts > 0 and channel_range < min_range:
            logger.debug(
                "Rompimento ignorado: range do canal (%.5f) abaixo do mínimo (%.5f).",
                channel_range,
                min_range,
            )
            return None

        current_close = signal_bar["close"]

        if current_close > channel_high:
            logger.info(
                "Sinal de COMPRA detectado (rompimento de %d barras: close=%.5f > máxima=%.5f).",
                config.lookback_bars,
                current_close,
                channel_high,
            )
            return Direction.BUY

        if current_close < channel_low:
            logger.info(
                "Sinal de VENDA detectado (rompimento de %d barras: close=%.5f < mínima=%.5f).",
                config.lookback_bars,
                current_close,
                channel_low,
            )
            return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: BreakoutNBarsConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna a máxima ou mínima do canal rompido como referência de entrada.

        Se o sinal mais recente foi de compra, retorna a máxima do canal.
        Caso contrário, retorna a mínima. Quando não há sinal recente, retorna o
        fechamento da última barra.
        """
        if len(df) < config.lookback_bars + 1:
            return float(df["close"].iloc[-1])

        channel_bars = df.iloc[-(config.lookback_bars + 1):-1]
        signal_bar = df.iloc[-1]
        channel_high = channel_bars["high"].max()
        channel_low = channel_bars["low"].min()
        current_close = signal_bar["close"]

        if current_close > channel_high:
            return float(channel_high)
        if current_close < channel_low:
            return float(channel_low)
        return float(current_close)
