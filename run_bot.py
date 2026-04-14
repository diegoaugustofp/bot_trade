"""
Ponto de Entrada do Trade Bot MT5
===================================

Dois modos de execução controlados pela variável de ambiente BOT_MODE:

  BOT_MODE=single  (padrão)
  ─────────────────────────
  Executa um único engine com o símbolo/estratégia do primeiro entry em
  bot_config.json (ou do entry cujo símbolo bata com SYMBOL).

      python run_bot.py
      SYMBOL=WINm25 python run_bot.py

  BOT_MODE=multi
  ──────────────
  Executa o BotOrchestrator com TODOS os entries definidos em bot_config.json.
  Cada entry pode ter símbolo e estratégia diferentes.

      BOT_MODE=multi python run_bot.py

Estratégias disponíveis (campo strategy_name em bot_config.json):
    "ma200_rejection"  — Recusa na MA200 (estratégia original)
    "ema_crossover"    — Cruzamento de EMAs rápida/lenta
    "pullback_trend"   — Pullback em tendência via EMA34
    "rsi_divergence"   — Divergência de RSI
    "breakout_nbars"   — Rompimento de N barras
    "macd_signal"      — Cruzamento MACD/Signal
    "poi"              — Recusa em Pontos de Interesse definidos pelo usuário

Configuração:
    1. Edite bot_config.json com seus símbolos, lotes e parâmetros de risco.
    2. Execute: python run_bot.py

Modo ONLINE vs. OFFLINE:
    ONLINE  — banco acessível via DATABASE_URL: configurações carregadas do DB.
              A busca é feita pelo par (symbol, strategy_name) — cada entrada do
              arquivo tem sua própria linha no banco. Se o par não existir ainda,
              ele é inserido automaticamente a partir do arquivo.
    OFFLINE — banco indisponível: configurações carregadas do bot_config.json.
              Os campos "runtime" (loop_interval, slippage, bars_to_fetch) são
              sempre lidos do arquivo, mesmo no modo ONLINE.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from trade_bot.db import BotDatabase
from trade_bot.engine import TradeBotEngine
from trade_bot.models import BotConfig
from trade_bot.orchestrator import BotOrchestrator, StrategyEntry
from trade_bot.strategies.base import BaseStrategy
from trade_bot.strategies.breakout_nbars import BreakoutNBarsConfig, BreakoutNBarsStrategy
from trade_bot.strategies.ema_crossover import EMACrossoverConfig, EMACrossoverStrategy
from trade_bot.strategies.ma200_rejection import MA200Config, MA200RejectionStrategy
from trade_bot.strategies.macd_signal import MACDSignalConfig, MACDSignalStrategy
from trade_bot.strategies.poi import POIConfig, POIStrategy
from trade_bot.strategies.pullback_trend import PullbackTrendConfig, PullbackTrendStrategy
from trade_bot.strategies.rsi_divergence import RSIDivergenceConfig, RSIDivergenceStrategy

_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trade_bot.log"),
        logging.StreamHandler(),
    ],
)

# ---------------------------------------------------------------------------
# Arquivo de configuração offline
# ---------------------------------------------------------------------------
_CONFIG_FILE = Path(__file__).parent / "bot_config.json"

# ---------------------------------------------------------------------------
# Mapeamento: strategy_name → (StrategyClass, ConfigClass)
# ---------------------------------------------------------------------------
_STRATEGY_FACTORIES: dict[str, tuple[type[BaseStrategy], type]] = {
    "ma200_rejection": (MA200RejectionStrategy, MA200Config),
    "ema_crossover":   (EMACrossoverStrategy,   EMACrossoverConfig),
    "pullback_trend":  (PullbackTrendStrategy,  PullbackTrendConfig),
    "rsi_divergence":  (RSIDivergenceStrategy,  RSIDivergenceConfig),
    "breakout_nbars":  (BreakoutNBarsStrategy,  BreakoutNBarsConfig),
    "macd_signal":     (MACDSignalStrategy,     MACDSignalConfig),
    "poi":             (POIStrategy,            POIConfig),
}

# ---------------------------------------------------------------------------
# Remapeamento de chaves do banco/dashboard → nomes de campo Python
#
# O dashboard armazena strategy_params com nomes de UI (ex.: "touch_threshold"),
# enquanto as classes Python usam "touch_threshold_pts". Esses remapeamentos são
# aplicados apenas quando a configuração vem do banco — no arquivo bot_config.json
# devem ser usados diretamente os nomes Python.
# ---------------------------------------------------------------------------
_DB_PARAM_REMAPS: dict[str, dict[str, str]] = {
    "ma200_rejection": {
        "touch_threshold": "touch_threshold_pts",
    },
    "ema_crossover": {
        "fast_period": "ema_fast_period",
        "slow_period": "ema_slow_period",
    },
    "pullback_trend": {
        "touch_threshold": "touch_threshold_pts",
    },
    "breakout_nbars": {
        "min_range": "min_range_pts",
    },
    "rsi_divergence": {},
    "macd_signal":    {},
    "poi": {
        "touch_threshold": "touch_threshold_pts",
    },
}

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _opt_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _opt_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _build_bot_config(sym: dict, runtime: dict) -> BotConfig:
    """Constrói BotConfig a partir de um entry do bot_config.json ou do banco."""
    return BotConfig(
        symbol=sym["symbol"],
        lot_size=float(sym.get("lot_size", 1.0)),
        timeframe_minutes=int(sym.get("timeframe_minutes", 5)),
        entry_offset=float(sym.get("entry_offset", 10.0)),
        stop_loss_pts=float(sym.get("stop_loss", 20.0)),
        partial1_pct=float(sym.get("partial1_percent", 60.0)) / 100.0,
        partial1_pts=float(sym.get("partial1_points", 20.0)),
        partial2_pct=float(sym.get("partial2_percent", 20.0)) / 100.0,
        partial2_pts=float(sym.get("partial2_points", 50.0)),
        partial3_pts=float(sym.get("partial3_points", 100.0)),
        max_open_trades=int(sym.get("max_open_trades", 3)),
        max_daily_stops=int(sym.get("max_daily_stops", 2)),
        trading_start_time=sym.get("trading_start_time"),
        trading_end_time=sym.get("trading_end_time"),
        force_close_time=sym.get("force_close_time"),
        max_daily_loss_pts=_opt_float(sym.get("max_daily_loss_pts")),
        max_daily_profit_pts=_opt_float(sym.get("max_daily_profit_pts")),
        break_even_pts=_opt_float(sym.get("break_even_pts")),
        cancel_pending_after_bars=_opt_int(sym.get("cancel_pending_after_bars")),
        # Runtime: sempre do arquivo JSON
        loop_interval=float(runtime.get("loop_interval", 10.0)),
        slippage=int(runtime.get("slippage", 5)),
        bars_to_fetch=int(runtime.get("bars_to_fetch", 300)),
    )


def _build_strategy_config(strategy_name: str, params: dict, *, from_db: bool = False):
    """Constrói a config específica da estratégia a partir de um dict de parâmetros.

    Parâmetros:
        strategy_name: Nome da estratégia (chave de _STRATEGY_FACTORIES).
        params: Dict de parâmetros — pode vir do JSON (nomes Python) ou do banco.
        from_db: Se True, aplica os remapeamentos de chaves antes de construir.
    """
    if strategy_name not in _STRATEGY_FACTORIES:
        raise ValueError(
            f"Estratégia desconhecida: '{strategy_name}'. "
            f"Opções: {list(_STRATEGY_FACTORIES.keys())}"
        )

    _, config_cls = _STRATEGY_FACTORIES[strategy_name]

    # Copia para não mutar o dict original
    p = dict(params)

    # Aplica remapeamentos de chaves do banco → Python se necessário
    if from_db:
        remaps = _DB_PARAM_REMAPS.get(strategy_name, {})
        for old_key, new_key in remaps.items():
            if old_key in p:
                p[new_key] = p.pop(old_key)
        # ma_type: normaliza para lowercase (DB pode guardar "SMA", classe espera "sma")
        if "ma_type" in p and isinstance(p["ma_type"], str):
            p["ma_type"] = p["ma_type"].lower()

    # Filtra apenas os campos que a classe conhece para evitar TypeError
    valid_fields = {f.name for f in dataclasses.fields(config_cls)}
    kwargs = {k: v for k, v in p.items() if k in valid_fields}

    return config_cls(**kwargs)


def _load_offline_config() -> list[dict]:
    """Lê bot_config.json e retorna a lista de entries (raw dicts).

    Lança FileNotFoundError se o arquivo não existir.
    Lança ValueError se a estrutura for inválida.
    """
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Arquivo de configuração não encontrado: {_CONFIG_FILE}\n"
            "  Crie o arquivo bot_config.json na raiz do projeto com pelo menos\n"
            "  um entry em 'symbols'. Consulte a documentação ou o exemplo\n"
            "  fornecido no repositório."
        )

    with _CONFIG_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    symbols = data.get("symbols")
    if not isinstance(symbols, list) or len(symbols) == 0:
        raise ValueError(
            "bot_config.json inválido: campo 'symbols' deve ser uma lista não vazia."
        )

    for i, entry in enumerate(symbols):
        if "symbol" not in entry:
            raise ValueError(
                f"bot_config.json: entry #{i} não tem o campo obrigatório 'symbol'."
            )
        if "strategy_name" not in entry:
            raise ValueError(
                f"bot_config.json: entry #{i} (símbolo={entry.get('symbol')}) "
                "não tem o campo obrigatório 'strategy_name'."
            )
        s_name = entry["strategy_name"]
        if s_name not in _STRATEGY_FACTORIES:
            raise ValueError(
                f"bot_config.json: entry #{i} (símbolo={entry.get('symbol')}) — "
                f"strategy_name '{s_name}' não reconhecido. "
                f"Opções válidas: {list(_STRATEGY_FACTORIES.keys())}"
            )

    return symbols


def _build_strategy_entry(sym_dict: dict) -> StrategyEntry:
    """Constrói um StrategyEntry a partir de um dict de configuração offline."""
    strategy_name = sym_dict["strategy_name"]
    runtime = sym_dict.get("runtime", {})
    params = sym_dict.get("strategy_params", {})

    if strategy_name not in _STRATEGY_FACTORIES:
        raise ValueError(
            f"Estratégia desconhecida: '{strategy_name}' no símbolo "
            f"'{sym_dict.get('symbol')}'. "
            f"Opções válidas: {list(_STRATEGY_FACTORIES.keys())}"
        )

    strategy_cls, _ = _STRATEGY_FACTORIES[strategy_name]
    bot_config = _build_bot_config(sym_dict, runtime)
    strategy_config = _build_strategy_config(strategy_name, params, from_db=False)

    return StrategyEntry(
        config=bot_config,
        strategy=strategy_cls(),
        strategy_config=strategy_config,
        strategy_name=strategy_name,
    )


def _get_db() -> tuple[Optional[BotDatabase], bool]:
    """Conecta ao banco a partir de DATABASE_URL.

    Retorna (BotDatabase, True) se conectado, (None, False) caso contrário.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logging.info(
            "DATABASE_URL não definida — modo OFFLINE. "
            "Defina esta variável para sincronizar com o painel web."
        )
        return None, False

    db = BotDatabase(database_url)
    if not db.connect():
        logging.warning(
            "Não foi possível conectar ao banco — modo OFFLINE. "
            "O painel não será atualizado em tempo real."
        )
        return None, False

    return db, True


def _apply_online_config(
    offline_entries: list[dict],
    db: BotDatabase,
) -> list[StrategyEntry]:
    """Sobrescreve configs com dados do banco onde possível.

    Para cada entry do arquivo offline (identificado pelo par symbol + strategy_name):
    - Se o par estiver no banco → usa a config do banco (exceto runtime).
    - Se o par NÃO estiver no banco → insere no banco e usa a config offline.

    Cada entry é pesquisado por (symbol, strategy_name) — não apenas por symbol —
    para suportar múltiplas estratégias configuradas no mesmo símbolo.

    Retorna lista de StrategyEntry prontos para execução.
    """
    final_entries: list[StrategyEntry] = []

    for sym_dict in offline_entries:
        symbol = sym_dict["symbol"]
        strategy_name = sym_dict["strategy_name"]
        runtime = sym_dict.get("runtime", {})

        # Busca exata por (símbolo, estratégia) — correto para multi-estratégia
        db_row = db.read_config_for_symbol_strategy(symbol, strategy_name)

        if db_row is None:
            # Par (símbolo, estratégia) não encontrado: inserir e usar config offline
            logging.info(
                "[ONLINE] '%s/%s' não encontrado no banco. "
                "Inserindo configuração do arquivo offline...",
                symbol, strategy_name,
            )
            db.insert_config_for_symbol(sym_dict)
            entry = _build_strategy_entry(sym_dict)
        else:
            # Par encontrado: usa parâmetros do banco (runtime sempre vem do arquivo)
            db_strategy = db_row.get("strategy_name") or strategy_name
            db_params = db_row.get("strategy_params") or {}

            if db_strategy not in _STRATEGY_FACTORIES:
                logging.error(
                    "[ONLINE] Estratégia '%s' do banco não reconhecida para '%s'. "
                    "Usando configuração offline.",
                    db_strategy, symbol,
                )
                entry = _build_strategy_entry(sym_dict)
            else:
                bot_config = _build_bot_config(db_row, runtime)
                strategy_config = _build_strategy_config(db_strategy, db_params, from_db=True)
                strategy_cls, _ = _STRATEGY_FACTORIES[db_strategy]
                entry = StrategyEntry(
                    config=bot_config,
                    strategy=strategy_cls(),
                    strategy_config=strategy_config,
                    strategy_name=db_strategy,
                )
                logging.info(
                    "[ONLINE] '%s/%s' carregado do banco (id=%s).",
                    symbol, db_strategy, db_row.get("id"),
                )

        final_entries.append(entry)

    return final_entries


def _run_single() -> None:
    """Modo single: executa um engine com o entry selecionado de bot_config.json.

    O entry é selecionado pela variável de ambiente SYMBOL (case-sensitive).
    Se SYMBOL não estiver definida, usa o primeiro entry do arquivo.
    """
    offline_entries = _load_offline_config()

    target_symbol = os.environ.get("SYMBOL")
    if target_symbol:
        matches = [e for e in offline_entries if e["symbol"] == target_symbol]
        if not matches:
            raise ValueError(
                f"Símbolo '{target_symbol}' (SYMBOL env var) não encontrado em "
                f"bot_config.json. Símbolos disponíveis: "
                f"{[e['symbol'] for e in offline_entries]}"
            )
        sym_dict = matches[0]
    else:
        sym_dict = offline_entries[0]
        logging.info(
            "SYMBOL não definida. Usando o primeiro entry do arquivo: %s",
            sym_dict["symbol"],
        )

    db, is_online = _get_db()

    if is_online:
        logging.info("[ONLINE] Configurações carregadas do banco de dados.")
        entries = _apply_online_config([sym_dict], db)
        entry = entries[0]
        entry.db = db
    else:
        logging.info("[OFFLINE] Banco indisponível. Usando configurações do arquivo bot_config.json.")
        entry = _build_strategy_entry(sym_dict)
        entry.db = None

    logging.info(
        "Modo SINGLE | símbolo=%s | estratégia=%s",
        entry.config.symbol,
        entry.strategy.__class__.__name__,
    )

    engine = TradeBotEngine(
        config=entry.config,
        strategy=entry.strategy,
        strategy_config=entry.strategy_config,
        strategy_name=entry.strategy_name,
        db=entry.db,
    )
    engine.run()


def _run_multi() -> None:
    """Modo multi: executa o BotOrchestrator com todos os entries de bot_config.json.

    Cada entry pode ter símbolo e estratégia diferentes.
    """
    offline_entries = _load_offline_config()

    if not offline_entries:
        raise ValueError(
            "bot_config.json não tem nenhum entry em 'symbols'. "
            "Adicione pelo menos um símbolo para usar BOT_MODE=multi."
        )

    database_url = os.environ.get("DATABASE_URL")
    db, is_online = _get_db()

    if is_online:
        logging.info("[ONLINE] Configurações carregadas do banco de dados.")
        final_entries = _apply_online_config(offline_entries, db)
        for entry in final_entries:
            if database_url:
                entry_db = BotDatabase(database_url)
                if entry_db.connect():
                    entry.db = entry_db
                else:
                    logging.warning(
                        "[ONLINE] Não foi possível criar conexão individual para %s/%s. "
                        "O painel não será atualizado para esta entrada.",
                        entry.config.symbol,
                        entry.strategy.__class__.__name__,
                    )
                    entry.db = None
    else:
        logging.info("[OFFLINE] Banco indisponível. Usando configurações do arquivo bot_config.json.")
        final_entries = [_build_strategy_entry(sym) for sym in offline_entries]
        for entry in final_entries:
            entry.db = None

    if db:
        db.close()

    orchestrator = BotOrchestrator(final_entries)
    orchestrator.run()


if __name__ == "__main__":
    bot_mode = os.environ.get("BOT_MODE", "single").lower()

    if bot_mode == "multi":
        logging.info("Modo de execução: MULTI (orquestrador)")
        _run_multi()
    else:
        symbol_hint = os.environ.get("SYMBOL", "(primeiro entry)")
        logging.info("Modo de execução: SINGLE (símbolo: %s)", symbol_hint)
        _run_single()
