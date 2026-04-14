"""
Integração com PostgreSQL — Trade Bot MT5
==========================================

Este módulo grava os dados do robô diretamente no banco PostgreSQL
compartilhado com o painel web. Com isso, o dashboard exibe operações
e status em tempo real sem necessidade de chamadas HTTP.

Configuração:
    Defina a variável de ambiente DATABASE_URL com a string de conexão
    do PostgreSQL, por exemplo:

        export DATABASE_URL="postgresql://user:senha@host:5432/dbname"

    No Windows (PowerShell):
        $env:DATABASE_URL = "postgresql://user:senha@host:5432/dbname"

    A DATABASE_URL pode ser obtida nas configurações do projeto no Replit
    (aba "Secrets" ou "Database").

Resiliência:
    Todos os erros de banco são capturados e registrados em log.
    Se o banco não estiver disponível, o robô continua operando normalmente
    — apenas sem sincronização com o painel.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False
    logger.warning(
        "psycopg2 não encontrado. Instale com: pip install psycopg2-binary\n"
        "O robô funcionará normalmente, mas sem sincronização com o banco."
    )


class BotDatabase:
    """Gerencia a conexão e as operações de escrita no PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._conn = None
        self._status_row_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------
    def connect(self) -> bool:
        """Abre conexão com o banco. Retorna True se bem-sucedido."""
        if not _PSYCOPG2_AVAILABLE:
            logger.error("psycopg2 não está instalado. Banco indisponível.")
            return False

        # Adiciona sslmode automaticamente se não informado na URL:
        #   - Conexões locais (localhost / 127.0.0.1): sslmode=disable
        #   - Conexões remotas (ex.: Neon.tech):       sslmode=require
        # Para sobrescrever, basta incluir ?sslmode=... na DATABASE_URL.
        url = self._url
        if "sslmode" not in url and "ssl=" not in url:
            _is_local = (
                "localhost" in url
                or "127.0.0.1" in url
                or "@localhost" in url
                or "@127.0.0.1" in url
            )
            sslmode = "disable" if _is_local else "require"
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}sslmode={sslmode}"

        try:
            self._conn = psycopg2.connect(url)
            self._conn.autocommit = True
            # Verifica se é banco interno do Replit (heliumdb)
            cur = self._conn.cursor()
            cur.execute("SELECT current_database();")
            dbname = cur.fetchone()[0]
            if dbname == "heliumdb":
                logger.error(
                    "Conectado ao banco INTERNO do Replit (%s).\n"
                    "  Este banco não é acessível de fora do Replit.\n"
                    "  Use um banco externo como Neon.tech (neon.tech):\n"
                    "  1. Crie uma conta gratuita em neon.tech\n"
                    "  2. Crie um projeto/banco de dados\n"
                    "  3. Copie a 'Connection String' (postgresql://...)\n"
                    "  4. Use esse endereço como DATABASE_URL no robô\n"
                    "     e também atualize a variável DATABASE_URL no Replit.",
                    dbname,
                )
                self._conn.close()
                self._conn = None
                return False
            logger.info("Conectado ao PostgreSQL (%s).", dbname)
            self._ensure_status_row()
            return True
        except Exception as exc:
            logger.error(
                "Falha ao conectar ao PostgreSQL: %s\n"
                "  Verifique a DATABASE_URL. Exemplos:\n"
                "    Local:   postgresql://usuario:senha@127.0.0.1:5432/nome_banco\n"
                "    Neon:    postgresql://usuario:senha@host.neon.tech/nome_banco\n"
                "  Se o erro for 'SSL required', adicione ?sslmode=disable (local)\n"
                "  ou ?sslmode=require (remoto) ao final da URL.",
                exc,
            )
            self._conn = None
            return False

    def close(self) -> None:
        """Fecha a conexão com o banco."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            logger.info("Conexão PostgreSQL encerrada.")

    def _cursor(self):
        """Retorna um cursor, reconectando se necessário."""
        if self._conn is None or self._conn.closed:
            logger.warning("Conexão perdida. Tentando reconectar...")
            self.connect()
        if self._conn is None:
            return None
        return self._conn.cursor()

    # ------------------------------------------------------------------
    # bot_status
    # ------------------------------------------------------------------
    def _ensure_status_row(self) -> None:
        """Garante que existe exatamente uma linha em bot_status."""
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute("SELECT id FROM bot_status ORDER BY id LIMIT 1;")
            row = cur.fetchone()
            if row:
                self._status_row_id = row[0]
            else:
                cur.execute(
                    "INSERT INTO bot_status (is_running, daily_stops) "
                    "VALUES (FALSE, 0) RETURNING id;"
                )
                self._status_row_id = cur.fetchone()[0]
                logger.info("Linha de bot_status criada (id=%d).", self._status_row_id)
        except Exception as exc:
            logger.error("Erro ao garantir linha de bot_status: %s", exc)

    def upsert_status(
        self,
        *,
        is_running: bool,
        daily_stops: int,
        current_price: Optional[float] = None,
        current_ma200: Optional[float] = None,
        last_signal_at: Optional[datetime] = None,
        block_reason: Optional[str] = None,
    ) -> None:
        """Atualiza o status do robô na tabela bot_status."""
        cur = self._cursor()
        if cur is None:
            return
        if self._status_row_id is None:
            self._ensure_status_row()
        if self._status_row_id is None:
            return
        try:
            cur.execute(
                """
                UPDATE bot_status SET
                    is_running   = %s,
                    daily_stops  = %s,
                    current_price = %s,
                    current_ma200 = %s,
                    last_signal_at = %s,
                    block_reason = %s,
                    updated_at   = NOW()
                WHERE id = %s;
                """,
                (
                    is_running,
                    daily_stops,
                    current_price,
                    current_ma200,
                    last_signal_at,
                    block_reason,
                    self._status_row_id,
                ),
            )
        except Exception as exc:
            logger.error("Erro ao atualizar bot_status: %s", exc)

    # ------------------------------------------------------------------
    # trades
    # ------------------------------------------------------------------
    def insert_trade(
        self,
        *,
        symbol: str,
        strategy_name: Optional[str] = None,
        direction: str,
        order_price: float,
        stop_loss: float,
        reference_price: float,
        lot_size: float,
        status: str = "pending",
    ) -> Optional[int]:
        """
        Insere uma nova operação na tabela trades.

        Retorna o ID gerado pelo banco, ou None em caso de erro.
        """
        cur = self._cursor()
        if cur is None:
            return None
        try:
            cur.execute(
                """
                INSERT INTO trades (
                    symbol, strategy_name, direction, order_price, stop_loss,
                    ma200_at_entry, lot_size, status,
                    partial1_closed, partial2_closed, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, FALSE, NOW())
                RETURNING id;
                """,
                (
                    symbol,
                    strategy_name,
                    direction,
                    order_price,
                    stop_loss,
                    reference_price,
                    lot_size,
                    status,
                ),
            )
            db_id = cur.fetchone()[0]
            logger.debug("Trade inserido no banco (id=%d).", db_id)
            return db_id
        except Exception as exc:
            logger.error("Erro ao inserir trade no banco: %s", exc)
            return None

    def activate_trade(
        self,
        db_id: int,
        *,
        entry_price: float,
        opened_at: datetime,
    ) -> None:
        """Marca uma ordem pendente como aberta no banco."""
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute(
                """
                UPDATE trades SET
                    status     = 'open',
                    entry_price = %s,
                    opened_at  = %s
                WHERE id = %s;
                """,
                (entry_price, opened_at, db_id),
            )
        except Exception as exc:
            logger.error("Erro ao ativar trade (id=%d): %s", db_id, exc)

    def mark_partial1_closed(self, db_id: int) -> None:
        """Registra o fechamento da 1ª parcial."""
        self._set_field(db_id, "partial1_closed", True)

    def mark_partial2_closed(self, db_id: int) -> None:
        """Registra o fechamento da 2ª parcial."""
        self._set_field(db_id, "partial2_closed", True)

    def close_trade(
        self,
        db_id: int,
        *,
        profit_loss: float,
        close_reason: str,
        closed_at: datetime,
    ) -> None:
        """Marca uma operação como fechada com PnL e motivo."""
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute(
                """
                UPDATE trades SET
                    status       = 'closed',
                    profit_loss  = %s,
                    close_reason = %s,
                    closed_at    = %s
                WHERE id = %s;
                """,
                (profit_loss, close_reason, closed_at, db_id),
            )
        except Exception as exc:
            logger.error("Erro ao fechar trade (id=%d): %s", db_id, exc)

    def cancel_trade(
        self,
        db_id: int,
        *,
        close_reason: str,
        closed_at: datetime,
    ) -> None:
        """Marca uma operação como cancelada."""
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute(
                """
                UPDATE trades SET
                    status       = 'cancelled',
                    close_reason = %s,
                    closed_at    = %s
                WHERE id = %s;
                """,
                (close_reason, closed_at, db_id),
            )
        except Exception as exc:
            logger.error("Erro ao cancelar trade (id=%d): %s", db_id, exc)

    # ------------------------------------------------------------------
    # bot_config
    # ------------------------------------------------------------------
    def read_configs_for_symbol(self, symbol: str) -> list[dict]:
        """Lê TODAS as configurações do banco para o símbolo dado.

        Retorna uma lista de dicts — uma por estratégia cadastrada para o
        símbolo. Retorna lista vazia se o símbolo não estiver cadastrado ou
        ocorrer algum erro.

        Substituiu read_config_for_symbol (que retornava LIMIT 1) para
        suportar múltiplas estratégias no mesmo símbolo.
        """
        cur = self._cursor()
        if cur is None:
            return []
        try:
            cur.execute(
                """
                SELECT
                    id, symbol, strategy_name, strategy_params,
                    lot_size, ma200_period, entry_offset, stop_loss,
                    partial1_percent, partial1_points,
                    partial2_percent, partial2_points, partial3_points,
                    max_open_trades, max_daily_stops, timeframe_minutes,
                    trading_start_time, trading_end_time, force_close_time,
                    max_daily_loss_pts, max_daily_profit_pts,
                    break_even_pts, cancel_pending_after_bars,
                    updated_at
                FROM bot_config
                WHERE symbol = %s
                ORDER BY id;
                """,
                (symbol,),
            )
            rows = cur.fetchall()
            if not rows:
                logger.warning("Nenhuma configuração encontrada para o símbolo '%s'.", symbol)
                return []
            columns = [
                "id", "symbol", "strategy_name", "strategy_params",
                "lot_size", "ma200_period", "entry_offset", "stop_loss",
                "partial1_percent", "partial1_points",
                "partial2_percent", "partial2_points", "partial3_points",
                "max_open_trades", "max_daily_stops", "timeframe_minutes",
                "trading_start_time", "trading_end_time", "force_close_time",
                "max_daily_loss_pts", "max_daily_profit_pts",
                "break_even_pts", "cancel_pending_after_bars",
                "updated_at",
            ]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            logger.error("Erro ao ler configurações para símbolo '%s': %s", symbol, exc)
            return []

    def read_config_for_symbol(self, symbol: str) -> Optional[dict]:
        """Lê a PRIMEIRA configuração do banco para o símbolo dado (compat.).

        Mantido para compatibilidade com código legado. Prefira
        read_config_for_symbol_strategy() ao trabalhar com múltiplas estratégias.
        """
        rows = self.read_configs_for_symbol(symbol)
        return rows[0] if rows else None

    def read_config_for_symbol_strategy(self, symbol: str, strategy_name: str) -> Optional[dict]:
        """Lê a configuração do banco para o par (símbolo, estratégia).

        Retorna um dict com todos os campos da linha correspondente, ou None
        se não existir nenhuma linha com esse par ou em caso de erro.
        Usado por _apply_online_config para obter a config exata da estratégia.
        """
        cur = self._cursor()
        if cur is None:
            return None
        try:
            cur.execute(
                """
                SELECT
                    id, symbol, strategy_name, strategy_params,
                    lot_size, ma200_period, entry_offset, stop_loss,
                    partial1_percent, partial1_points,
                    partial2_percent, partial2_points, partial3_points,
                    max_open_trades, max_daily_stops, timeframe_minutes,
                    trading_start_time, trading_end_time, force_close_time,
                    max_daily_loss_pts, max_daily_profit_pts,
                    break_even_pts, cancel_pending_after_bars,
                    updated_at
                FROM bot_config
                WHERE symbol = %s AND strategy_name = %s
                LIMIT 1;
                """,
                (symbol, strategy_name),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [
                "id", "symbol", "strategy_name", "strategy_params",
                "lot_size", "ma200_period", "entry_offset", "stop_loss",
                "partial1_percent", "partial1_points",
                "partial2_percent", "partial2_points", "partial3_points",
                "max_open_trades", "max_daily_stops", "timeframe_minutes",
                "trading_start_time", "trading_end_time", "force_close_time",
                "max_daily_loss_pts", "max_daily_profit_pts",
                "break_even_pts", "cancel_pending_after_bars",
                "updated_at",
            ]
            return dict(zip(columns, row))
        except Exception as exc:
            logger.error(
                "Erro ao ler configuração para '%s/%s': %s", symbol, strategy_name, exc
            )
            return None

    def insert_config_for_symbol(self, config_dict: dict) -> bool:
        """Insere uma configuração de símbolo no banco se ainda não existir.

        Recebe um dict com os campos do arquivo bot_config.json. Não sobrescreve
        uma configuração existente — se o símbolo já está no banco, retorna False
        sem alterar nada.

        Parâmetros:
            config_dict: Dicionário com os campos do símbolo (mesma estrutura do
                arquivo bot_config.json, com as chaves do DB: stop_loss, partial1_percent, etc.).

        Retorna True se inseriu com sucesso, False caso contrário.
        """
        cur = self._cursor()
        if cur is None:
            return False
        symbol = config_dict.get("symbol", "")
        strategy_name = config_dict.get("strategy_name", "ma200_rejection")
        try:
            cur.execute(
                "SELECT id FROM bot_config WHERE symbol = %s AND strategy_name = %s LIMIT 1;",
                (symbol, strategy_name),
            )
            if cur.fetchone() is not None:
                logger.debug(
                    "Símbolo '%s' com estratégia '%s' já existe no banco — insert_config_for_symbol ignorado.",
                    symbol, strategy_name,
                )
                return False

            strategy_params = config_dict.get("strategy_params") or {}
            cur.execute(
                """
                INSERT INTO bot_config (
                    symbol, strategy_name, strategy_params,
                    lot_size, ma200_period, entry_offset, stop_loss,
                    partial1_percent, partial1_points,
                    partial2_percent, partial2_points, partial3_points,
                    max_open_trades, max_daily_stops, timeframe_minutes,
                    trading_start_time, trading_end_time, force_close_time,
                    max_daily_loss_pts, max_daily_profit_pts,
                    break_even_pts, cancel_pending_after_bars
                ) VALUES (
                    %s, %s, %s::jsonb,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s
                );
                """,
                (
                    symbol,
                    config_dict.get("strategy_name", "ma200_rejection"),
                    json.dumps(strategy_params),
                    float(config_dict.get("lot_size", 1.0)),
                    int(config_dict.get("ma200_period", 200)),
                    float(config_dict.get("entry_offset", 10.0)),
                    float(config_dict.get("stop_loss", 20.0)),
                    float(config_dict.get("partial1_percent", 60.0)),
                    float(config_dict.get("partial1_points", 20.0)),
                    float(config_dict.get("partial2_percent", 20.0)),
                    float(config_dict.get("partial2_points", 50.0)),
                    float(config_dict.get("partial3_points", 100.0)),
                    int(config_dict.get("max_open_trades", 3)),
                    int(config_dict.get("max_daily_stops", 2)),
                    int(config_dict.get("timeframe_minutes", 5)),
                    config_dict.get("trading_start_time"),
                    config_dict.get("trading_end_time"),
                    config_dict.get("force_close_time"),
                    config_dict.get("max_daily_loss_pts"),
                    config_dict.get("max_daily_profit_pts"),
                    config_dict.get("break_even_pts"),
                    config_dict.get("cancel_pending_after_bars"),
                ),
            )
            logger.info(
                "Símbolo '%s' inserido no banco a partir da configuração offline.",
                symbol,
            )
            return True
        except Exception as exc:
            logger.error(
                "Erro ao inserir configuração do símbolo '%s' no banco: %s", symbol, exc
            )
            return False

    # ------------------------------------------------------------------
    # global_settings (configurações globais)
    # ------------------------------------------------------------------
    def _ensure_settings_row(self) -> None:
        """Garante que existe exatamente uma linha em global_settings."""
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS global_settings (
                    id SERIAL PRIMARY KEY,
                    discord_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("SELECT id FROM global_settings LIMIT 1;")
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO global_settings (discord_enabled) VALUES (FALSE);"
                )
        except Exception as exc:
            logger.error("Erro ao garantir linha de global_settings: %s", exc)

    def read_discord_enabled(self) -> bool:
        """Lê a flag discord_enabled do banco. Retorna False em caso de erro."""
        cur = self._cursor()
        if cur is None:
            return False
        try:
            self._ensure_settings_row()
            cur.execute("SELECT discord_enabled FROM global_settings LIMIT 1;")
            row = cur.fetchone()
            return bool(row[0]) if row else False
        except Exception as exc:
            logger.error("Erro ao ler discord_enabled: %s", exc)
            return False

    def set_discord_enabled(self, enabled: bool) -> bool:
        """Atualiza a flag discord_enabled no banco. Retorna True se bem-sucedido."""
        cur = self._cursor()
        if cur is None:
            return False
        try:
            self._ensure_settings_row()
            cur.execute(
                "UPDATE global_settings SET discord_enabled = %s, updated_at = NOW();",
                (enabled,),
            )
            return True
        except Exception as exc:
            logger.error("Erro ao atualizar discord_enabled: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Utilitário
    # ------------------------------------------------------------------
    def _set_field(self, db_id: int, field: str, value) -> None:
        cur = self._cursor()
        if cur is None:
            return
        try:
            cur.execute(
                f"UPDATE trades SET {field} = %s WHERE id = %s;",
                (value, db_id),
            )
        except Exception as exc:
            logger.error("Erro ao atualizar campo %s do trade %d: %s", field, db_id, exc)
