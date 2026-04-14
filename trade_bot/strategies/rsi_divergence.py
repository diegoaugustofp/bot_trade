"""
Estratégia: Divergência de RSI
================================

Lógica:
    Detecta divergências entre o preço e o Índice de Força Relativa (RSI):

    - Divergência de ALTA (COMPRA): O preço faz uma mínima mais baixa do que
      a mínima anterior, mas o RSI faz uma mínima mais ALTA (divergência de alta).
      Indica exaustão de venda e potencial reversão para cima.

    - Divergência de BAIXA (VENDA): O preço faz uma máxima mais alta do que
      a máxima anterior, mas o RSI faz uma máxima mais BAIXA (divergência de baixa).
      Indica exaustão de compra e potencial reversão para baixo.

    A busca de pivôs usa a janela lookback_bars para encontrar as mínimas/máximas
    mais recentes dentro desse período.

Parâmetros (RSIDivergenceConfig):
    rsi_period (int): Período para o cálculo do RSI. Padrão: 14.
    lookback_bars (int): Número de barras para buscar pivôs de preço e RSI. Padrão: 20.
    rsi_overbought (float): Nível de sobrecompra do RSI. Padrão: 70.0.
    rsi_oversold (float): Nível de sobrevenda do RSI. Padrão: 30.0.

Exemplo de uso:
    from trade_bot.strategies.rsi_divergence import RSIDivergenceStrategy, RSIDivergenceConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=RSIDivergenceStrategy(),
        strategy_config=RSIDivergenceConfig(rsi_period=14, lookback_bars=20),
    )
    engine.run()
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from trade_bot.models import Direction
from trade_bot.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class RSIDivergenceConfig:
    """Parâmetros da estratégia de divergência de RSI.

    Atributos:
        rsi_period: Período do RSI. Padrão: 14.
        lookback_bars: Janela de busca de pivôs. Padrão: 20.
        rsi_overbought: Nível de sobrecompra; divergência de baixa é considerada
            apenas quando o RSI esteve próximo deste nível. Padrão: 70.0.
        rsi_oversold: Nível de sobrevenda; divergência de alta é considerada
            apenas quando o RSI esteve próximo deste nível. Padrão: 30.0.
    """
    rsi_period: int = 14
    lookback_bars: int = 20
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0


def _calculate_rsi(closes: pd.Series, period: int) -> pd.Series:
    """Calcula o RSI usando a fórmula de Wilder (média móvel exponencial)."""
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


class RSIDivergenceStrategy(BaseStrategy):
    """Detecta sinal de entrada com base em divergências entre preço e RSI."""

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: RSIDivergenceConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme divergência de RSI detectada.

        Parâmetros:
            df: DataFrame OHLCV com barras fechadas.
            config: Instância de RSIDivergenceConfig.
            point_value: Não utilizado nesta estratégia (mantido por interface).

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        min_bars = config.rsi_period + config.lookback_bars + 1
        if len(df) < min_bars:
            return None

        df = df.copy()
        df["rsi"] = _calculate_rsi(df["close"], config.rsi_period)
        valid = df.dropna(subset=["rsi"]).reset_index(drop=True)

        if len(valid) < config.lookback_bars + 1:
            return None

        window = valid.iloc[-(config.lookback_bars):]

        last_bar = window.iloc[-1]
        current_low = last_bar["low"]
        current_rsi_low = last_bar["rsi"]
        current_high = last_bar["high"]
        current_rsi_high = last_bar["rsi"]

        prev_window = window.iloc[:-1]

        if len(prev_window) == 0:
            return None

        prev_low_idx = prev_window["low"].idxmin()
        prev_low = prev_window.loc[prev_low_idx, "low"]
        prev_rsi_at_low = prev_window.loc[prev_low_idx, "rsi"]

        if (current_low < prev_low and
                current_rsi_low > prev_rsi_at_low and
                current_rsi_low < config.rsi_oversold + 15):
            logger.info(
                "Sinal de COMPRA detectado (divergência de alta: preço mínima mais baixa, "
                "RSI mínima mais alta | RSI atual=%.1f).",
                current_rsi_low,
            )
            return Direction.BUY

        prev_high_idx = prev_window["high"].idxmax()
        prev_high = prev_window.loc[prev_high_idx, "high"]
        prev_rsi_at_high = prev_window.loc[prev_high_idx, "rsi"]

        if (current_high > prev_high and
                current_rsi_high < prev_rsi_at_high and
                current_rsi_high > config.rsi_overbought - 15):
            logger.info(
                "Sinal de VENDA detectado (divergência de baixa: preço máxima mais alta, "
                "RSI máxima mais baixa | RSI atual=%.1f).",
                current_rsi_high,
            )
            return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: RSIDivergenceConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o fechamento da última barra como referência de entrada."""
        return float(df["close"].iloc[-1])
