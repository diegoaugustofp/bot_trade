"""
Classe Base para Estratégias do Trade Bot MT5
=============================================

Define a interface que todas as estratégias devem implementar.

Para criar uma nova estratégia:
1. Crie um arquivo em trade_bot/strategies/minha_estrategia.py
2. Defina um dataclass com os parâmetros da estratégia (valores em pontos do símbolo)
3. Crie uma classe que herda de BaseStrategy
4. Implemente os métodos detect_signal() e get_reference_price()

Parâmetros com sufixo _pts nos dataclasses de estratégias são sempre expressos
em ticks do símbolo (trade_tick_size — o menor incremento negociável de preço).
O engine passa point_value (= trade_tick_size) para que as estratégias convertam
ticks → unidades de preço:
    threshold_price = config.touch_threshold_pts * point_value

Exemplo:
    from dataclasses import dataclass
    from typing import Optional
    import pandas as pd
    from trade_bot.strategies.base import BaseStrategy
    from trade_bot.models import Direction

    @dataclass
    class MinhaConfig:
        periodo: int = 20
        distancia_pts: float = 10.0  # em ticks (trade_tick_size) do símbolo

    class MinhaEstrategia(BaseStrategy):
        def detect_signal(
            self,
            df: pd.DataFrame,
            config: MinhaConfig,
            point_value: float = 1.0,
        ) -> Optional[Direction]:
            threshold = config.distancia_pts * point_value
            ...

        def get_reference_price(
            self,
            df: pd.DataFrame,
            config: MinhaConfig,
            point_value: float = 1.0,
        ) -> float:
            return df["close"].iloc[-1]
"""

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from trade_bot.models import Direction


class BaseStrategy(ABC):
    """Interface abstrata para estratégias de detecção de sinal.

    Toda estratégia deve implementar dois métodos:
    - detect_signal: retorna a direção do sinal (BUY/SELL) ou None se não há sinal.
    - get_reference_price: retorna o preço de referência a partir do qual o engine
      calcula o preço de entrada da ordem limite (ref ± entry_offset).

    O argumento point_value é o valor de um ponto do símbolo em unidades de preço
    (ex.: para WINM25 no MT5, point = 5.0). Parâmetros com sufixo _pts nos
    dataclasses de configuração são expressos em pontos; a conversão para preço
    deve ser feita multiplicando por point_value dentro das estratégias.
    """

    @abstractmethod
    def detect_signal(
        self,
        df: pd.DataFrame,
        config: object,
        point_value: float = 1.0,
    ) -> Optional[Direction]:
        """Analisa o DataFrame e retorna o sinal de entrada ou None.

        Parâmetros:
            df: DataFrame com colunas OHLCV (open, high, low, close, tick_volume).
                Por padrão contém apenas barras fechadas (a barra em formação é
                excluída pelo engine). Exceção: quando o dataclass de configuração
                da estratégia define ``rejection_candles=0``, o engine inclui o
                candle em formação como última linha do df — o sinal pode então
                ser disparado no toque, sem aguardar o fechamento do candle.
                Estratégias que não suportam esse modo devem ignorar ou rejeitar
                configurações com rejection_candles=0.
            config: Dataclass de configuração específico desta estratégia.
            point_value: Valor de um ponto do símbolo em unidades de preço.
                Obtido via mt5.symbol_info(symbol).point no engine.

        Retorno:
            Direction.BUY, Direction.SELL, ou None se não há sinal.
        """

    @abstractmethod
    def get_reference_price(
        self,
        df: pd.DataFrame,
        config: object,
        point_value: float = 1.0,
    ) -> float:
        """Retorna o preço de referência para a ordem limite.

        O engine aplicará entry_offset (em pontos) a este preço para calcular o
        preço final da ordem (ex.: MA200, EMA, nível de suporte/resistência, etc.).

        Parâmetros:
            df: Mesmo DataFrame passado para detect_signal.
            config: Mesmo objeto de configuração passado para detect_signal.
            point_value: Valor de um ponto do símbolo em unidades de preço.

        Retorno:
            Preço de referência como float.
        """
