# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

## Artifacts

### Trade Bot Dashboard (`artifacts/trade-dashboard`)
- A web dashboard to monitor and configure the MetaTrader 5 MA200 rejection strategy bot
- Pages: `/` (Dashboard), `/trades` (History), `/config` (Configuration)
- Dark navy trading terminal aesthetic
- Auto-refreshes every 5s using TanStack Query

### API Server (`artifacts/api-server`)
- Routes: `/api/bot/config`, `/api/bot/status`, `/api/bot/trades`, `/api/bot/summary`
- DB tables: `bot_config`, `bot_status`, `trades`

## Trade Bot Python Script

The `trade_bot_mt5.py` file in the project root is the MetaTrader 5 Python bot.

### Strategy: MA200 Rejection
- **Timeframe**: M5 (5 minutes)
- **Signal**: Price touches MA200 and rejects
- **Entry**: 10 points above/below the MA200 (limit order)
- **Stop**: 20 points
- **Partials**:
  - 1st: 60% of position at +20 pts
  - 2nd: 20% at +50 pts
  - 3rd: remaining 20% at +100 pts
- **Cancellation**: If price crosses stop before order activation, order is cancelled
- **Risk**: Max 3 open trades; blocks after 2 daily stops

### Requirements
```bash
pip install MetaTrader5 pandas numpy
```

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.
