"""
Estratégia: Pullback em Tendência
===================================

Lógica:
    Utiliza a EMA34 para determinar a tendência atual e aguarda um pullback
    (recuo do preço até a média) seguido de retomada na direção da tendência:

    1. Confirma tendência via EMA34:
       - ALTA: as últimas confirmation_candles barras fecham ACIMA da EMA.
       - BAIXA: as últimas confirmation_candles barras fecham ABAIXO da EMA.

    2. Detecta o pullback (toque na EMA):
       - Em tendência de alta: alguma das barras do lookback recente tem o low
         tocando a EMA (low ≤ EMA + touch_threshold_pts * point_value).
       - Em tendência de baixa: alguma das barras tem o high tocando a EMA
         (high ≥ EMA - touch_threshold_pts * point_value).

    3. Confirma retomada:
       - Em alta: após o toque, os candles de confirmação fecham acima da EMA.
         Sinal: COMPRA.
       - Em baixa: após o toque, os candles de confirmação fecham abaixo da EMA.
         Sinal: VENDA.

Parâmetros (PullbackTrendConfig):
    trend_ema_period (int): Período da EMA de tendência. Padrão: 34.
    touch_threshold_pts (float): Distância máxima em pontos do símbolo para
        considerar que o preço "tocou" a EMA. Convertido para unidades de preço
        multiplicando por point_value. Padrão: 8.0.
    confirmation_candles (int): Candles após o toque que devem fechar do lado
        correto da EMA para confirmar a retomada. Também usado para confirmar
        o estado de tendência antes do pullback. Padrão: 2.
    trend_lookback (int): Número de barras antes do toque usadas para confirmar
        a tendência prévia. Padrão: 5.

Exemplo de uso:
    from trade_bot.strategies.pullback_trend import PullbackTrendStrategy, PullbackTrendConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=PullbackTrendStrategy(),
        strategy_config=PullbackTrendConfig(trend_ema_period=34, touch_threshold_pts=8.0),
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
class PullbackTrendConfig:
    """Parâmetros da estratégia de pullback em tendência.

    Atributos:
        trend_ema_period: Período da EMA de tendência. Padrão: 34.
        touch_threshold_pts: Distância máxima em pontos do símbolo entre o
            low/high e a EMA para ser considerado toque. Convertido para
            unidades de preço multiplicando por point_value. Padrão: 8.0.
        confirmation_candles: Barras após o toque que confirmam a retomada.
            Também usadas para confirmar trend_lookback anteriores ao toque.
            Padrão: 2.
        trend_lookback: Número de barras antes do toque verificadas para
            confirmar que a tendência estava estabelecida. As barras desse
            período devem fechar majoritariamente do lado correto da EMA.
            Padrão: 5.
    """
    trend_ema_period: int = 34
    touch_threshold_pts: float = 8.0
    confirmation_candles: int = 2
    trend_lookback: int = 5


class PullbackTrendStrategy(BaseStrategy):
    """Detecta sinal de entrada em pullbacks dentro de tendências via EMA34.

    O sinal só é emitido quando:
    1. Tendência prévia confirmada: a maioria das barras do período trend_lookback
       (antes do toque) fecha do mesmo lado da EMA.
    2. Toque na EMA detectado na barra logo antes das barras de confirmação.
    3. Retomada confirmada: as barras de confirmação fecham do lado original da EMA.
    """

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: PullbackTrendConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme pullback na EMA de tendência.

        Parâmetros:
            df: DataFrame OHLCV com barras fechadas.
            config: Instância de PullbackTrendConfig.
            point_value: Valor de um ponto do símbolo em unidades de preço.
                Usado para converter touch_threshold_pts em unidades de preço.

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        n = config.confirmation_candles
        look = config.trend_lookback
        min_bars = config.trend_ema_period + look + n + 2
        if len(df) < min_bars:
            return None

        df = df.copy()
        df["ema"] = df["close"].ewm(span=config.trend_ema_period, adjust=False).mean()
        valid = df.dropna(subset=["ema"]).reset_index(drop=True)

        if len(valid) < look + n + 2:
            return None

        threshold = config.touch_threshold_pts * point_value

        touch_idx = -(n + 1)
        touch_bar = valid.iloc[touch_idx]
        ema_at_touch = touch_bar["ema"]

        trend_bars = valid.iloc[touch_idx - look : touch_idx]
        if len(trend_bars) < look:
            return None

        bars_above = sum(1 for _, row in trend_bars.iterrows() if row["close"] > row["ema"])
        bars_below = look - bars_above

        conf_bars = valid.iloc[-n:]

        uptrend = bars_above > bars_below
        downtrend = bars_below > bars_above

        if uptrend:
            touched = touch_bar["low"] <= ema_at_touch + threshold

            if touched:
                all_above = all(
                    conf_bars.iloc[i]["close"] > conf_bars.iloc[i]["ema"]
                    for i in range(n)
                )
                if all_above:
                    logger.info(
                        "Sinal de COMPRA detectado (tendência de alta + pullback + retomada "
                        "na EMA%d | acima=%d/%d barras de tendência).",
                        config.trend_ema_period,
                        bars_above,
                        look,
                    )
                    return Direction.BUY

        if downtrend:
            touched = touch_bar["high"] >= ema_at_touch - threshold

            if touched:
                all_below = all(
                    conf_bars.iloc[i]["close"] < conf_bars.iloc[i]["ema"]
                    for i in range(n)
                )
                if all_below:
                    logger.info(
                        "Sinal de VENDA detectado (tendência de baixa + pullback + retomada "
                        "na EMA%d | abaixo=%d/%d barras de tendência).",
                        config.trend_ema_period,
                        bars_below,
                        look,
                    )
                    return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: PullbackTrendConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o valor atual da EMA de tendência como referência de entrada."""
        ema = df["close"].ewm(span=config.trend_ema_period, adjust=False).mean()
        return float(ema.iloc[-1])
