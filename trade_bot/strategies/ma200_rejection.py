"""
Estratégia: Recusa na MA200
============================

Lógica:
    O preço (mínimo ou máximo de um candle) toca a Média Móvel de 200 períodos
    dentro de um threshold configurável. Nos candles seguintes, o preço se afasta
    da MA na direção esperada, confirmando a recusa.

    - COMPRA: preço estava ACIMA da MA, o LOW de um candle toca a MA e os candles
      seguintes fecham ACIMA da MA (rejeição/bounce para cima).
    - VENDA:  preço estava ABAIXO da MA, o HIGH de um candle toca a MA e os candles
      seguintes fecham ABAIXO da MA (rejeição/bounce para baixo).

    Filtro de distância mínima (min_distance_pts):
    Quando ativo (> 0), a estratégia só considera um toque válido se o preço
    já esteve a pelo menos N ticks de distância da MA em algum momento dentro
    das barras disponíveis. Evita falsos sinais durante lateralizações sobre
    a MA, onde a estratégia de recusa não é efetiva.

Parâmetros (MA200Config):
    ma_period (int): Período da média móvel. Padrão: 200.
    ma_type (str): Tipo da média móvel — ``"sma"`` (Simples, padrão) ou ``"ema"`` (Exponencial).
    touch_threshold_pts (float): Distância máxima em ticks (trade_tick_size) entre
        o low/high do candle e a MA para ser considerado um toque. Padrão: 5.0.
    rejection_candles (int): Número de candles consecutivos para confirmar a recusa. Padrão: 2.
    min_distance_pts (float): Distância mínima em ticks que o preço deve ter se
        afastado da MA antes de ativar a detecção de toque. 0 = desativado. Padrão: 0.0.

Exemplo de uso:
    from trade_bot.strategies.ma200_rejection import MA200RejectionStrategy, MA200Config
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=MA200RejectionStrategy(),
        strategy_config=MA200Config(
            ma_period=200,
            touch_threshold_pts=5.0,
            rejection_candles=2,
            min_distance_pts=30.0,  # só ativa após 30 ticks de afastamento
        ),
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
class MA200Config:
    """Parâmetros da estratégia de recusa na MA200.

    Atributos:
        ma_period: Período da média móvel. Padrão: 200.
        ma_type: Tipo da média móvel. Valores válidos: ``"sma"`` (Média Móvel
            Simples, padrão) ou ``"ema"`` (Média Móvel Exponencial).
        touch_threshold_pts: Distância máxima em ticks (trade_tick_size) entre
            o low/high do candle de toque e a MA para ser considerado um toque
            válido. O engine passa point_value (= tick_size) para converter
            ticks em unidades de preço. Padrão: 5.0.
        rejection_candles: Quantidade de candles após o toque que devem fechar
            do mesmo lado da MA para confirmar a recusa. Use 0 para sinalizar
            imediatamente no toque (candle em formação). Padrão: 2.
        min_distance_pts: Distância mínima em ticks (trade_tick_size) que o
            preço deve ter se afastado da MA antes de a detecção de toque ser
            ativada. Evita falsos sinais quando o preço anda de lado sobre a MA.
            0.0 = filtro desativado (qualquer toque é considerado). Valores
            típicos: 20–50 para WIN/WDO. Padrão: 0.0.
    """
    ma_period: int = 200
    ma_type: str = "sma"
    touch_threshold_pts: float = 5.0
    rejection_candles: int = 2
    min_distance_pts: float = 0.0

    _VALID_MA_TYPES = ("sma", "ema")

    def __post_init__(self) -> None:
        if self.ma_type not in self._VALID_MA_TYPES:
            raise ValueError(
                f"ma_type inválido: '{self.ma_type}'. "
                f"Valores aceitos: {self._VALID_MA_TYPES}"
            )
        if self.min_distance_pts < 0:
            raise ValueError(
                f"min_distance_pts deve ser >= 0. Recebido: {self.min_distance_pts}"
            )


class MA200RejectionStrategy(BaseStrategy):
    """Detecta recusa de preço na Média Móvel de 200 períodos."""

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: MA200Config,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Retorna BUY, SELL ou None conforme a detecção de recusa na MA200.

        Regras de sinal:
        - BUY:  preço vinha de CIMA da MA → LOW do candle de toque chegou à MA
                dentro do threshold → candles de confirmação fecham ACIMA da MA.
        - SELL: preço vinha de BAIXO da MA → HIGH do candle de toque chegou à MA
                dentro do threshold → candles de confirmação fecham ABAIXO da MA.

        O candle pré-toque (barra imediatamente antes do candle de toque) é usado
        para verificar de qual lado o preço vinha antes do toque.

        Parâmetros:
            df: DataFrame OHLCV. Quando rejection_candles=0 o engine passa o
                df completo (incluindo o candle em formação) e o sinal dispara
                no toque da MA, sem aguardar confirmação. Para rejection_candles>=1
                o df contém apenas barras fechadas e a confirmação é exigida.
            config: Instância de MA200Config.
            point_value: Valor de um tick do símbolo em unidades de preço
                (trade_tick_size passado pelo engine). Usado para converter
                touch_threshold_pts e min_distance_pts em unidades de preço.

        Retorno:
            Direction.BUY, Direction.SELL, ou None.
        """
        rej_candles = config.rejection_candles

        if rej_candles == 0:
            logger.debug(
                "MA200 modo candle vivo (rejection_candles=0) — "
                "sinal dispara no toque sem confirmação."
            )

        if len(df) < config.ma_period + rej_candles + 2:
            return None

        df = df.copy()
        if config.ma_type == "ema":
            df["ma200"] = df["close"].ewm(span=config.ma_period, adjust=False).mean()
        else:
            df["ma200"] = df["close"].rolling(config.ma_period).mean()
        valid = df.dropna(subset=["ma200"]).reset_index(drop=True)

        # Precisamos do candle pré-toque: touch_idx - 1
        # Para rej_candles=0: touch=-1, pre_touch=-2 → precisamos de 2 linhas (rej+2)
        # Para rej_candles=2: touch=-3, pre_touch=-4 → precisamos de 4 linhas (rej+2)
        if len(valid) < rej_candles + 2:
            return None

        # ------------------------------------------------------------------
        # Filtro de distância mínima
        # Verificado na janela das últimas ma_period barras para refletir
        # apenas o comportamento recente (evita ativação por afastamentos antigos).
        # ------------------------------------------------------------------
        if config.min_distance_pts > 0:
            min_dist_price = config.min_distance_pts * point_value
            recent = valid.tail(config.ma_period)
            max_dist = (recent["close"] - recent["ma200"]).abs().max()
            if max_dist < min_dist_price:
                logger.debug(
                    "MA200 filtro min_distance: distância máxima nas últimas %d barras "
                    "%.4f < %.4f (%.1f ticks). Aguardando afastamento antes de ativar.",
                    config.ma_period,
                    max_dist,
                    min_dist_price,
                    config.min_distance_pts,
                )
                return None

        threshold = config.touch_threshold_pts * point_value

        touch_idx = -(rej_candles + 1)
        touch_bar = valid.iloc[touch_idx]
        pre_touch_bar = valid.iloc[touch_idx - 1]
        ma_touch = touch_bar["ma200"]

        # MA da barra pré-toque (mais preciso que usar ma_touch para classificar o lado)
        ma_pre_touch = pre_touch_bar["ma200"]

        # Preço vinha de CIMA: barra pré-toque fechou acima da SUA MA e o LOW do
        # candle de toque desceu até a área da MA do candle de toque.
        came_from_above = (
            pre_touch_bar["close"] > ma_pre_touch
            and abs(touch_bar["low"] - ma_touch) <= threshold
        )

        # Preço vinha de BAIXO: barra pré-toque fechou abaixo da SUA MA e o HIGH do
        # candle de toque subiu até a área da MA do candle de toque.
        came_from_below = (
            pre_touch_bar["close"] < ma_pre_touch
            and abs(touch_bar["high"] - ma_touch) <= threshold
        )

        if not (came_from_above or came_from_below):
            return None

        # Para rejection_candles=0, range(0) é vazio e all() retorna True
        # imediatamente — o toque no candle vivo já basta para sinalizar.
        conf_bars = valid.iloc[-rej_candles:] if rej_candles > 0 else valid.iloc[0:0]

        if came_from_above:
            # Confirmação: candles após o toque fecham ACIMA da MA (bounce para cima)
            all_above = all(
                conf_bars.iloc[i]["close"] > valid.iloc[touch_idx + 1 + i]["ma200"]
                for i in range(rej_candles)
            )
            if all_above:
                if rej_candles == 0:
                    logger.info(
                        "Sinal de COMPRA detectado "
                        "(toque MA200 pelo alto no candle vivo, sem confirmação)."
                    )
                else:
                    logger.info(
                        "Sinal de COMPRA detectado "
                        "(recusa na MA200 — preço veio de cima, bounce para cima)."
                    )
                return Direction.BUY

        if came_from_below:
            # Confirmação: candles após o toque fecham ABAIXO da MA (rejeitado para baixo)
            all_below = all(
                conf_bars.iloc[i]["close"] < valid.iloc[touch_idx + 1 + i]["ma200"]
                for i in range(rej_candles)
            )
            if all_below:
                if rej_candles == 0:
                    logger.info(
                        "Sinal de VENDA detectado "
                        "(toque MA200 pela base no candle vivo, sem confirmação)."
                    )
                else:
                    logger.info(
                        "Sinal de VENDA detectado "
                        "(recusa na MA200 — preço veio de baixo, rejeitado para baixo)."
                    )
                return Direction.SELL

        return None

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: MA200Config,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o valor atual da MA200 para calcular o preço de entrada."""
        closes = df["close"].values
        if config.ma_type == "ema":
            ma = float(
                pd.Series(closes).ewm(span=config.ma_period, adjust=False).mean().iloc[-1]
            )
        else:
            ma = float(np.mean(closes[-config.ma_period:]))
        return ma
