"""
Orquestrador Multi-Estratégia do Trade Bot MT5
================================================

Executa múltiplos pares (símbolo, estratégia) em paralelo via threads,
com bloqueio por símbolo: se qualquer estratégia tiver posição aberta ou
pendente em um símbolo, nenhuma outra estratégia abre nova entrada naquele
mesmo símbolo.

Uso típico em run_bot.py (BOT_MODE=multi):

    from trade_bot.orchestrator import BotOrchestrator, StrategyEntry
    from trade_bot.models import BotConfig
    from trade_bot.strategies.ma200_rejection import MA200RejectionStrategy, MA200Config
    from trade_bot.strategies.ema_crossover import EMACrossoverStrategy, EMACrossoverConfig
    from trade_bot.strategies.macd_signal import MACDSignalStrategy, MACDSignalConfig

    entries = [
        StrategyEntry(
            config=BotConfig(symbol="WINM25", lot_size=1.0, ...),
            strategy=MA200RejectionStrategy(),
            strategy_config=MA200Config(),
        ),
        StrategyEntry(
            config=BotConfig(symbol="WINM25", lot_size=1.0, ...),
            strategy=EMACrossoverStrategy(),
            strategy_config=EMACrossoverConfig(),
        ),
        StrategyEntry(
            config=BotConfig(symbol="PETR4", lot_size=1.0, ...),
            strategy=MACDSignalStrategy(),
            strategy_config=MACDSignalConfig(),
        ),
    ]

    orchestrator = BotOrchestrator(entries)
    orchestrator.run()

Arquitetura do bloqueio por símbolo:
-------------------------------------
- `_symbol_locks`  : um threading.Lock por símbolo (acesso exclusivo ao contador).
- `_symbol_busy`   : contador de trades ativos (open + pending) por símbolo,
                     compartilhado entre todas as engines via o gate.
- Antes de enviar uma ordem limite, a engine chama `try_acquire_symbol`,
  que verifica E reserva o símbolo atomicamente sob um único lock,
  eliminando a race condition TOCTOU. Se ocupado, retorna False e o sinal
  é ignorado naquele ciclo.
- Se o order_send falhar após a aquisição, a engine chama `release_trade`
  para liberar a reserva.
- Ao fechar ou cancelar um trade, `release_trade` decrementa o contador.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5

from trade_bot.engine import TradeBotEngine
from trade_bot.models import BotConfig
from trade_bot.strategies.base import BaseStrategy
from trade_bot.db import BotDatabase

logger = logging.getLogger(__name__)


@dataclass
class StrategyEntry:
    """Agrupa uma configuração de símbolo com sua estratégia para execução paralela."""

    config: BotConfig
    strategy: BaseStrategy
    strategy_config: object
    strategy_name: Optional[str] = None
    db: Optional[BotDatabase] = None


class BotOrchestrator:
    """
    Gerencia múltiplos TradeBotEngines em threads paralelas, implementando a
    interface SymbolGate para garantir exclusividade de entrada por símbolo.

    Parâmetros:
        entries: Lista de StrategyEntry a serem executadas em paralelo.
    """

    def __init__(self, entries: list[StrategyEntry]) -> None:
        self._entries = entries
        self._stop_event = threading.Event()

        symbols = {e.config.symbol for e in entries}
        self._symbol_locks: dict[str, threading.Lock] = {
            s: threading.Lock() for s in symbols
        }
        self._symbol_busy: dict[str, int] = {s: 0 for s in symbols}

    # ------------------------------------------------------------------
    # Interface SymbolGate
    # ------------------------------------------------------------------

    def try_acquire_symbol(self, symbol: str) -> bool:
        """
        Verifica atomicamente se o símbolo está livre e, se estiver, reserva-o
        (incrementa o contador sob o mesmo lock). Retorna True se adquirido,
        False se já havia trade ativo no símbolo.

        A operação check+reserve ocorre sob um único lock para eliminar a
        race condition TOCTOU que existiria entre um is_symbol_free separado
        e um register_trade separado.
        """
        lock = self._symbol_locks.get(symbol)
        if lock is None:
            return True
        with lock:
            if self._symbol_busy.get(symbol, 0) > 0:
                return False
            self._symbol_busy[symbol] = 1
        logger.debug("[gate] %s reservado (1 trade ativo)", symbol)
        return True

    def release_trade(self, symbol: str) -> None:
        """
        Libera um slot do símbolo (decrementa contador, mínimo 0).
        Deve ser chamado ao fechar/cancelar um trade ou quando order_send
        falha após uma aquisição bem-sucedida.
        """
        lock = self._symbol_locks.get(symbol)
        if lock is None:
            return
        with lock:
            self._symbol_busy[symbol] = max(0, self._symbol_busy.get(symbol, 0) - 1)
            remaining = self._symbol_busy[symbol]
        logger.debug("[gate] %s liberado — %d trade(s) ativo(s)", symbol, remaining)

    # ------------------------------------------------------------------
    # Execução interna (por thread)
    # ------------------------------------------------------------------

    def _run_entry(self, entry: StrategyEntry) -> None:
        """Cria e executa um TradeBotEngine dentro de uma thread."""
        logger.info(
            "[orch] Iniciando engine: símbolo=%s | estratégia=%s",
            entry.config.symbol,
            entry.strategy.__class__.__name__,
        )
        engine = TradeBotEngine(
            config=entry.config,
            strategy=entry.strategy,
            strategy_config=entry.strategy_config,
            strategy_name=entry.strategy_name,
            db=entry.db,
            skip_connect=True,
            symbol_gate=self,
            stop_event=self._stop_event,
        )
        try:
            engine.run()
        except Exception:
            logger.exception(
                "[orch] Engine encerrou com erro inesperado: símbolo=%s | estratégia=%s",
                entry.config.symbol,
                entry.strategy.__class__.__name__,
            )

    # ------------------------------------------------------------------
    # Ponto de entrada principal
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Conecta ao MT5 no thread principal, lança todas as threads de engine
        e aguarda encerramento. Captura KeyboardInterrupt para parada limpa.
        """
        logger.info("=" * 60)
        logger.info(
            "[orch] BotOrchestrator iniciando — %d entradas em %d símbolo(s).",
            len(self._entries),
            len(self._symbol_locks),
        )
        logger.info("=" * 60)

        if not mt5.initialize():
            logger.error("[orch] Falha ao inicializar MT5: %s", mt5.last_error())
            return

        account = mt5.account_info()
        if account is None:
            logger.error(
                "[orch] Conta MT5 não encontrada. Verifique o login no terminal."
            )
            mt5.shutdown()
            return

        logger.info(
            "[orch] MT5 conectado | Conta: %s | Saldo: %.2f %s",
            account.login,
            account.balance,
            account.currency,
        )

        threads: list[threading.Thread] = []
        for entry in self._entries:
            name = f"{entry.config.symbol}-{entry.strategy.__class__.__name__}"
            t = threading.Thread(
                target=self._run_entry,
                args=(entry,),
                name=name,
                daemon=True,
            )
            threads.append(t)

        try:
            for t in threads:
                t.start()
                logger.info("[orch] Thread iniciada: %s", t.name)

            for t in threads:
                t.join()

        except KeyboardInterrupt:
            logger.info(
                "[orch] Interrompido pelo usuário. Sinalizando parada para todas as threads."
            )
            self._stop_event.set()
            for t in threads:
                t.join(timeout=30)
                if t.is_alive():
                    logger.warning(
                        "[orch] Thread '%s' não encerrou em 30 s.", t.name
                    )
        finally:
            mt5.shutdown()
            logger.info("[orch] Conexão MT5 encerrada pelo orquestrador.")
