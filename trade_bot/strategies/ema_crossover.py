"""
Estratégia: Cruzamento de EMAs
================================

Lógica:
    Calcula duas Médias Móveis Exponenciais — uma rápida e uma lenta. Quando a
    EMA rápida cruza a EMA lenta, é gerado um sinal de entrada:

    - COMPRA: EMA rápida cruza para CIMA da EMA lenta.
    - VENDA:  EMA rápida cruza para BAIXO da EMA lenta.

    O parâmetro confirmation_candles exige que, após o cruzamento, os candles
    confirmem que a EMA rápida permanece acima/abaixo da EMA lenta. Com
    confirmation_candles=1 (padrão), basta o cruzamento ocorrer na última barra.

Parâmetros (EMACrossoverConfig):
    ema_fast_period (int): Período da EMA rápida. Padrão: 9.
    ema_slow_period (int): Período da EMA lenta. Padrão: 21.
    confirmation_candles (int): Número de barras após o cruzamento para confirmar. Padrão: 1.

Exemplo de uso:
    from trade_bot.strategies.ema_crossover import EMACrossoverStrategy, EMACrossoverConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=EMACrossoverStrategy(),
        strategy_config=EMACrossoverConfig(ema_fast_period=9, ema_slow_period=21),
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
class EMACrossoverConfig:
    """Parâmetros da estratégia de cruzamento de EMAs.

    Atributos:
        ema_fast_period: Período da EMA rápida. Padrão: 9.
        ema_slow_period: Período da EMA lenta. Padrão: 21.
        confirmation_candles: Barras consecutivas após o cruzamento onde a EMA
            rápida deve permanecer acima/abaixo da EMA lenta. Padrão: 1.
    """
    ema_fast_period: int = 9
    ema_slow_period: int = 21
    confirmation_candles: int = 1


class EMACrossoverStrategy(BaseStrategy):
    """Detecta sinal de entrada com base no cruzamento de duas EMAs."""

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: EMACrossoverConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme o cruzamento das EMAs.

        Parâmetros:
            df: DataFrame OHLCV com barras fechadas.
            config: Instância de EMACrossoverConfig.
            point_value: Não utilizado nesta estratégia (mantido por interface).

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        min_bars = config.ema_slow_period + config.confirmation_candles + 1
        if len(df) < min_bars:
            return None

        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=config.ema_fast_period, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=config.ema_slow_period, adjust=False).mean()

        n = config.confirmation_candles

        conf_bars = df.iloc[-(n):]
        pre_bar = df.iloc[-(n + 1)]

        fast_pre = pre_bar["ema_fast"]
        slow_pre = pre_bar["ema_slow"]

        all_fast_above = all(
            conf_bars.iloc[i]["ema_fast"] > conf_bars.iloc[i]["ema_slow"]
            for i in range(n)
        )
        all_fast_below = all(
            conf_bars.iloc[i]["ema_fast"] < conf_bars.iloc[i]["ema_slow"]
            for i in range(n)
        )

        if all_fast_above and fast_pre <= slow_pre:
            logger.info(
                "Sinal de COMPRA detectado (EMA%d cruzou EMA%d para cima).",
                config.ema_fast_period,
                config.ema_slow_period,
            )
            return Direction.BUY

        if all_fast_below and fast_pre >= slow_pre:
            logger.info(
                "Sinal de VENDA detectado (EMA%d cruzou EMA%d para baixo).",
                config.ema_fast_period,
                config.ema_slow_period,
            )
            return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: EMACrossoverConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o valor da EMA lenta na última barra como referência de entrada."""
        ema_slow = df["close"].ewm(span=config.ema_slow_period, adjust=False).mean()
        return float(ema_slow.iloc[-1])
