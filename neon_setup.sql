-- Script de criação das tabelas no banco externo (Neon.tech)
-- Execute este script no SQL Editor do Neon após criar seu banco de dados.

    CREATE TABLE IF NOT EXISTS bot_config (
        id          SERIAL PRIMARY KEY,
        symbol      TEXT NOT NULL DEFAULT 'WINM25',
        strategy_name   TEXT NOT NULL DEFAULT 'ma200_rejection',
        strategy_params JSONB NOT NULL DEFAULT '{}',
        lot_size    REAL NOT NULL DEFAULT 1.0,
        ma200_period INTEGER NOT NULL DEFAULT 200,
        entry_offset REAL NOT NULL DEFAULT 10.0,
        stop_loss    REAL NOT NULL DEFAULT 20.0,
        partial1_percent REAL NOT NULL DEFAULT 60.0,
        partial1_points  REAL NOT NULL DEFAULT 20.0,
        partial2_percent REAL NOT NULL DEFAULT 20.0,
        partial2_points  REAL NOT NULL DEFAULT 50.0,
        partial3_points  REAL NOT NULL DEFAULT 100.0,
        max_open_trades  INTEGER NOT NULL DEFAULT 3,
        max_daily_stops  INTEGER NOT NULL DEFAULT 2,
        timeframe_minutes INTEGER NOT NULL DEFAULT 5,
        trading_start_time    TEXT,
        trading_end_time      TEXT,
        force_close_time      TEXT,
        max_daily_loss_pts    REAL,
        max_daily_profit_pts  REAL,
        break_even_pts        REAL,
        cancel_pending_after_bars INTEGER,
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT bot_config_symbol_unique UNIQUE (symbol)
    );
    
    CREATE TABLE IF NOT EXISTS bot_status (
        id            SERIAL PRIMARY KEY,
        is_running    BOOLEAN NOT NULL DEFAULT FALSE,
        daily_stops   INTEGER NOT NULL DEFAULT 0,
        current_ma200 REAL,
        current_price REAL,
        last_signal_at TIMESTAMPTZ,
        block_reason  TEXT,
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS trades (
        id              SERIAL PRIMARY KEY,
        symbol          TEXT NOT NULL,
        direction       TEXT NOT NULL,
        order_price     REAL NOT NULL,
        entry_price     REAL,
        stop_loss       REAL NOT NULL,
        ma200_at_entry  REAL NOT NULL,
        lot_size        REAL NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending',
        partial1_closed BOOLEAN NOT NULL DEFAULT FALSE,
        partial2_closed BOOLEAN NOT NULL DEFAULT FALSE,
        profit_loss     REAL,
        close_reason    TEXT,
        opened_at       TIMESTAMPTZ,
        closed_at       TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    -- Inserir configuração padrão
    INSERT INTO bot_config (symbol) VALUES ('WINM25')
    ON CONFLICT (symbol) DO NOTHING;
