"""
Estratégia: Pontos de Interesse (POI)
======================================

Lógica:
    O usuário define listas de preços de compra e de venda para o ativo.
    Quando o preço toca um desses níveis (dentro de um threshold configurável)
    vindo do lado correto, e em seguida o rejeita (candles de confirmação
    fecham do lado esperado), uma ordem limite é gerada.

    - COMPRA: preço estava ACIMA do nível, o LOW de um candle toca o nível
      dentro do threshold e os candles seguintes fecham ACIMA do nível.
      (nível age como suporte — preço veio de cima e rejeitou para cima)

    - VENDA:  preço estava ABAIXO do nível, o HIGH de um candle toca o nível
      dentro do threshold e os candles seguintes fecham ABAIXO do nível.
      (nível age como resistência — preço veio de baixo e rejeitou para baixo)

    A verificação de qual lado o preço vinha é feita usando a barra anterior
    ao candle de toque (pré-toque). A condição de toque é bilateral:
    abs(field - level) <= threshold, evitando disparos quando o preço está
    longe do nível mas ainda satisfaz uma condição unilateral.

    Cada nível é válido para apenas 1 entrada. Após disparar um sinal, o nível
    é marcado como consumido e ignorado nas iterações seguintes.

Parâmetros (POIConfig):
    buy_levels (list[float]): Preços onde se espera recusa de COMPRA (suportes).
    sell_levels (list[float]): Preços onde se espera recusa de VENDA (resistências).
    touch_threshold_pts (float): Distância máxima em ticks (trade_tick_size) para
        considerar "toque" no nível. Convertido para unidades de preço via
        point_value. Padrão: 5.0.
    rejection_candles (int): Quantidade de candles consecutivos após o toque
        que devem fechar do mesmo lado para confirmar a recusa. Padrão: 2.

Exemplo de uso:
    from trade_bot.strategies.poi import POIStrategy, POIConfig
    from trade_bot.engine import TradeBotEngine
    from trade_bot.models import BotConfig

    engine = TradeBotEngine(
        config=BotConfig(symbol="WINM25"),
        strategy=POIStrategy(),
        strategy_config=POIConfig(
            buy_levels=[125000.0, 124500.0],
            sell_levels=[126000.0, 126500.0],
            touch_threshold_pts=5.0,
            rejection_candles=2,
        ),
    )
    engine.run()
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from trade_bot.models import Direction
from trade_bot.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


@dataclass
class POIConfig:
    """Parâmetros da estratégia de Pontos de Interesse.

    Atributos:
        buy_levels: Lista de preços onde se espera recusa de COMPRA (suportes).
            O nível é tocado pelo LOW do candle vindo de cima.
            Exemplo: [125000.0, 124500.0]
        sell_levels: Lista de preços onde se espera recusa de VENDA (resistências).
            O nível é tocado pelo HIGH do candle vindo de baixo.
            Exemplo: [126000.0, 126500.0]
        touch_threshold_pts: Distância máxima em ticks (trade_tick_size) para
            considerar que o preço "tocou" o nível. Condição bilateral:
            abs(low/high - level) <= threshold. Convertido para unidades de
            preço multiplicando por point_value. Padrão: 5.0.
        rejection_candles: Quantidade de candles consecutivos após o toque que
            devem fechar do mesmo lado para confirmar a recusa. Padrão: 2.
    """
    buy_levels: list = field(default_factory=list)
    sell_levels: list = field(default_factory=list)
    touch_threshold_pts: float = 5.0
    rejection_candles: int = 2


class POIStrategy(BaseStrategy):
    """Detecta recusa de preço em Pontos de Interesse definidos pelo usuário.

    Estado interno:
        _consumed_buy: conjunto de preços de compra já utilizados (1 entrada cada).
        _consumed_sell: conjunto de preços de venda já utilizados (1 entrada cada).
        _last_signal_level: nível que gerou o sinal mais recente — usado por
            get_reference_price() para retornar o preço de referência da ordem.
    """

    def __init__(self) -> None:
        self._consumed_buy: set = set()
        self._consumed_sell: set = set()
        self._last_signal_level: float = 0.0

    # ------------------------------------------------------------------
    # Detecção de sinal
    # ------------------------------------------------------------------

    def detect_signal(
        self,
        df: pd.DataFrame,
        config: POIConfig,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Verifica se o preço recusou em algum nível de interesse.

        Regras de toque:
        - BUY:  barra pré-toque fechou ACIMA do nível E abs(touch_bar["low"]  - level) <= threshold
        - SELL: barra pré-toque fechou ABAIXO do nível E abs(touch_bar["high"] - level) <= threshold

        Parâmetros:
            df: DataFrame OHLCV. Quando rejection_candles=0 o engine passa o
                df completo (incluindo o candle em formação) e o sinal dispara
                no toque, sem aguardar confirmação. Para rejection_candles>=1
                o df contém apenas barras fechadas.
            config: Instância de POIConfig com os níveis definidos.
            point_value: Valor de um tick (trade_tick_size) em unidades de preço.

        Retorno:
            Direction.BUY, Direction.SELL, ou None se não há sinal.
        """
        rej_candles = config.rejection_candles

        # rejection_candles=0: entrada no candle vivo, sem confirmação
        if rej_candles == 0:
            return self._detect_live_bar(df, config, point_value)

        # Precisamos do candle pré-toque + candle de toque + rej_candles de confirmação
        # touch_idx = -(rej_candles+1), pre_touch_idx = -(rej_candles+2)
        # min_bars = rej_candles + 2 garante que ambos existam
        min_bars = rej_candles + 2
        if len(df) < min_bars:
            logger.debug("Barras insuficientes para POI (%d < %d).", len(df), min_bars)
            return None

        threshold = config.touch_threshold_pts * point_value

        # Índice do candle de toque (logo antes dos candles de confirmação)
        touch_idx = -(rej_candles + 1)
        touch_bar = df.iloc[touch_idx]
        pre_touch_bar = df.iloc[touch_idx - 1]
        conf_bars = df.iloc[-rej_candles:]

        # --- Verifica níveis de COMPRA (suportes) ---
        # Preço veio de CIMA: pré-toque fechou acima do nível,
        # LOW do toque desceu até o nível (bilateral), confirma bounce para cima.
        for level in config.buy_levels:
            if level in self._consumed_buy:
                continue

            touched = (
                pre_touch_bar["close"] > level
                and abs(touch_bar["low"] - level) <= threshold
            )

            if not touched:
                continue

            # Confirmação: todos os candles de confirmação fecham acima do nível
            all_above = all(bar["close"] > level for _, bar in conf_bars.iterrows())

            if all_above:
                logger.info(
                    "Sinal de COMPRA detectado "
                    "(recusa POI em %.5f — preço veio de cima).", level
                )
                self._consumed_buy.add(level)
                self._last_signal_level = level
                return Direction.BUY

        # --- Verifica níveis de VENDA (resistências) ---
        # Preço veio de BAIXO: pré-toque fechou abaixo do nível,
        # HIGH do toque subiu até o nível (bilateral), confirma rejeição para baixo.
        for level in config.sell_levels:
            if level in self._consumed_sell:
                continue

            touched = (
                pre_touch_bar["close"] < level
                and abs(touch_bar["high"] - level) <= threshold
            )

            if not touched:
                continue

            # Confirmação: todos os candles de confirmação fecham abaixo do nível
            all_below = all(bar["close"] < level for _, bar in conf_bars.iterrows())

            if all_below:
                logger.info(
                    "Sinal de VENDA detectado "
                    "(recusa POI em %.5f — preço veio de baixo).", level
                )
                self._consumed_sell.add(level)
                self._last_signal_level = level
                return Direction.SELL

        return None

    def _detect_live_bar(
        self,
        df: pd.DataFrame,
        config: POIConfig,
        point_value: float,
    ) -> Optional[Direction]:
        """Detecção no candle vivo (rejection_candles=0): sem confirmação.

        O candle em formação (último do df) é usado como barra de toque.
        A barra anterior (df.iloc[-2]) serve de pré-toque para validar o lado.
        O sinal dispara imediatamente ao toque no nível, sem aguardar
        candles de fechamento confirmatórios.

        Regras de toque (modo vivo):
        - BUY:  pré-toque fechou ACIMA do nível E abs(live_bar["low"]  - level) <= threshold
        - SELL: pré-toque fechou ABAIXO do nível E abs(live_bar["high"] - level) <= threshold
        """
        if len(df) < 2:
            return None

        threshold = config.touch_threshold_pts * point_value
        live_bar = df.iloc[-1]
        pre_touch_bar = df.iloc[-2]

        logger.debug(
            "POI candle vivo | low=%.5f  high=%.5f  threshold=%.5f  "
            "pre_touch_close=%.5f",
            live_bar["low"], live_bar["high"], threshold,
            pre_touch_bar["close"],
        )

        # --- Níveis de COMPRA ---
        # Preço veio de cima: pré-toque fechou acima do nível, LOW toca o nível
        for level in config.buy_levels:
            if level in self._consumed_buy:
                continue
            if (
                pre_touch_bar["close"] > level
                and abs(live_bar["low"] - level) <= threshold
            ):
                logger.info(
                    "Sinal de COMPRA detectado "
                    "(toque POI candle vivo em %.5f — preço veio de cima).", level
                )
                self._consumed_buy.add(level)
                self._last_signal_level = level
                return Direction.BUY

        # --- Níveis de VENDA ---
        # Preço veio de baixo: pré-toque fechou abaixo do nível, HIGH toca o nível
        for level in config.sell_levels:
            if level in self._consumed_sell:
                continue
            if (
                pre_touch_bar["close"] < level
                and abs(live_bar["high"] - level) <= threshold
            ):
                logger.info(
                    "Sinal de VENDA detectado "
                    "(toque POI candle vivo em %.5f — preço veio de baixo).", level
                )
                self._consumed_sell.add(level)
                self._last_signal_level = level
                return Direction.SELL

        return None

    # ------------------------------------------------------------------
    # Preço de referência para a ordem
    # ------------------------------------------------------------------

    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: POIConfig,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o nível POI que gerou o sinal como preço de referência.

        O engine aplicará entry_offset a partir deste preço para calcular o
        preço final da ordem limite.
        """
        if self._last_signal_level:
            return self._last_signal_level
        # Fallback: preço de fechamento mais recente
        return float(df["close"].iloc[-1])

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def reset_consumed(self) -> None:
        """Limpa todos os níveis consumidos (ex.: início de nova sessão)."""
        self._consumed_buy.clear()
        self._consumed_sell.clear()
        self._last_signal_level = 0.0
        logger.info("POIStrategy: níveis consumidos foram resetados.")

    @property
    def consumed_buy(self) -> set:
        """Níveis de compra já utilizados."""
        return set(self._consumed_buy)

    @property
    def consumed_sell(self) -> set:
        """Níveis de venda já utilizados."""
        return set(self._consumed_sell)
