import { Router, type IRouter } from "express";
import { eq, desc, count, asc, and } from "drizzle-orm";
import { db, botConfigTable, tradesTable, botStatusTable, globalSettingsTable } from "@workspace/db";
import {
  GetBotConfigResponse,
  UpdateBotConfigBody,
  UpdateBotConfigResponse,
  GetBotStatusResponse,
  ListTradesQueryParams,
  ListTradesResponse,
  GetTradeParams,
  GetTradeResponse,
  GetBotSummaryResponse,
  ListSymbolConfigsResponse,
  CreateSymbolConfigBody,
  GetSymbolConfigParams,
  GetSymbolConfigResponse,
  UpdateSymbolConfigByIdParams,
  UpdateSymbolConfigBody,
  UpdateSymbolConfigResponse,
  DeleteSymbolConfigByIdParams,
  GetBotSettingsResponse,
  UpdateBotSettingsBody,
} from "@workspace/api-zod";

const router: IRouter = Router();

// ---------------------------------------------------------------------------
// Helper: map a DB row to the SymbolConfig response shape
// ---------------------------------------------------------------------------
function rowToSymbolConfig(row: typeof botConfigTable.$inferSelect) {
  return {
    id: row.id,
    symbol: row.symbol,
    strategyName: row.strategyName,
    strategyParams: (row.strategyParams as Record<string, unknown>) ?? {},
    lotSize: row.lotSize,
    ma200Period: row.ma200Period,
    entryOffset: row.entryOffset,
    stopLoss: row.stopLoss,
    partial1Percent: row.partial1Percent,
    partial1Points: row.partial1Points,
    partial2Percent: row.partial2Percent,
    partial2Points: row.partial2Points,
    partial3Points: row.partial3Points,
    maxOpenTrades: row.maxOpenTrades,
    maxDailyStops: row.maxDailyStops,
    timeframeMinutes: row.timeframeMinutes,
    tradingStartTime: row.tradingStartTime ?? null,
    tradingEndTime: row.tradingEndTime ?? null,
    forceCloseTime: row.forceCloseTime ?? null,
    maxDailyLossPts: row.maxDailyLossPts ?? null,
    maxDailyProfitPts: row.maxDailyProfitPts ?? null,
    breakEvenPts: row.breakEvenPts ?? null,
    cancelPendingAfterBars: row.cancelPendingAfterBars ?? null,
    updatedAt: row.updatedAt.toISOString(),
  };
}

async function ensureDefaultConfig() {
  const existing = await db.select().from(botConfigTable).limit(1);
  if (existing.length === 0) {
    await db.insert(botConfigTable).values({
      symbol: "WINM25",
      strategyName: "ma200_rejection",
      strategyParams: {},
      lotSize: 1.0,
      ma200Period: 200,
      entryOffset: 10.0,
      stopLoss: 20.0,
      partial1Percent: 60.0,
      partial1Points: 20.0,
      partial2Percent: 20.0,
      partial2Points: 50.0,
      partial3Points: 100.0,
      maxOpenTrades: 3,
      maxDailyStops: 2,
      timeframeMinutes: 5,
    });
  }
}

async function ensureDefaultStatus() {
  const existing = await db.select().from(botStatusTable).limit(1);
  if (existing.length === 0) {
    await db.insert(botStatusTable).values({
      isRunning: false,
      dailyStops: 0,
    });
  }
}

// ---------------------------------------------------------------------------
// NEW: GET /bot/configs — list all symbol configurations
// ---------------------------------------------------------------------------
router.get("/bot/configs", async (req, res): Promise<void> => {
  const rows = await db
    .select()
    .from(botConfigTable)
    .orderBy(asc(botConfigTable.symbol));

  res.json(ListSymbolConfigsResponse.parse(rows.map(rowToSymbolConfig)));
});

// ---------------------------------------------------------------------------
// NEW: POST /bot/configs — create a new symbol configuration
// ---------------------------------------------------------------------------
router.post("/bot/configs", async (req, res): Promise<void> => {
  const parsed = CreateSymbolConfigBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const existing = await db
    .select({ id: botConfigTable.id })
    .from(botConfigTable)
    .where(
      and(
        eq(botConfigTable.symbol, parsed.data.symbol),
        eq(botConfigTable.strategyName, parsed.data.strategyName ?? "ma200_rejection"),
      )
    )
    .limit(1);

  if (existing.length > 0) {
    res.status(409).json({
      error: `Já existe uma configuração para o símbolo '${parsed.data.symbol}' com a estratégia '${parsed.data.strategyName ?? "ma200_rejection"}'.`,
    });
    return;
  }

  const [created] = await db
    .insert(botConfigTable)
    .values({
      symbol: parsed.data.symbol,
      strategyName: parsed.data.strategyName ?? "ma200_rejection",
      strategyParams: parsed.data.strategyParams ?? {},
      lotSize: parsed.data.lotSize,
      ma200Period: parsed.data.ma200Period,
      entryOffset: parsed.data.entryOffset,
      stopLoss: parsed.data.stopLoss,
      partial1Percent: parsed.data.partial1Percent,
      partial1Points: parsed.data.partial1Points,
      partial2Percent: parsed.data.partial2Percent,
      partial2Points: parsed.data.partial2Points,
      partial3Points: parsed.data.partial3Points,
      maxOpenTrades: parsed.data.maxOpenTrades,
      maxDailyStops: parsed.data.maxDailyStops,
      timeframeMinutes: parsed.data.timeframeMinutes,
      tradingStartTime: parsed.data.tradingStartTime ?? null,
      tradingEndTime: parsed.data.tradingEndTime ?? null,
      forceCloseTime: parsed.data.forceCloseTime ?? null,
      maxDailyLossPts: parsed.data.maxDailyLossPts ?? null,
      maxDailyProfitPts: parsed.data.maxDailyProfitPts ?? null,
      breakEvenPts: parsed.data.breakEvenPts ?? null,
      cancelPendingAfterBars: parsed.data.cancelPendingAfterBars ?? null,
    })
    .returning();

  res.status(201).json(GetSymbolConfigResponse.parse(rowToSymbolConfig(created)));
});

// ---------------------------------------------------------------------------
// NEW: GET /bot/configs/:symbol — get a specific symbol configuration
// ---------------------------------------------------------------------------
router.get("/bot/configs/:symbol", async (req, res): Promise<void> => {
  const params = GetSymbolConfigParams.safeParse({ symbol: req.params.symbol });
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [row] = await db
    .select()
    .from(botConfigTable)
    .where(eq(botConfigTable.symbol, params.data.symbol))
    .limit(1);

  if (!row) {
    res.status(404).json({ error: `Symbol '${params.data.symbol}' not found` });
    return;
  }

  res.json(GetSymbolConfigResponse.parse(rowToSymbolConfig(row)));
});

// ---------------------------------------------------------------------------
// NEW: PUT /bot/configs/:id — update a configuration by numeric ID
// ---------------------------------------------------------------------------
router.put("/bot/configs/:id", async (req, res): Promise<void> => {
  const params = UpdateSymbolConfigByIdParams.safeParse({ id: req.params.id });
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const parsed = UpdateSymbolConfigBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const existing = await db
    .select({ id: botConfigTable.id })
    .from(botConfigTable)
    .where(eq(botConfigTable.id, params.data.id))
    .limit(1);

  if (existing.length === 0) {
    res.status(404).json({ error: `Config id '${params.data.id}' not found` });
    return;
  }

  const [updated] = await db
    .update(botConfigTable)
    .set({
      strategyName: parsed.data.strategyName ?? "ma200_rejection",
      strategyParams: parsed.data.strategyParams ?? {},
      lotSize: parsed.data.lotSize,
      ma200Period: parsed.data.ma200Period,
      entryOffset: parsed.data.entryOffset,
      stopLoss: parsed.data.stopLoss,
      partial1Percent: parsed.data.partial1Percent,
      partial1Points: parsed.data.partial1Points,
      partial2Percent: parsed.data.partial2Percent,
      partial2Points: parsed.data.partial2Points,
      partial3Points: parsed.data.partial3Points,
      maxOpenTrades: parsed.data.maxOpenTrades,
      maxDailyStops: parsed.data.maxDailyStops,
      timeframeMinutes: parsed.data.timeframeMinutes,
      tradingStartTime: parsed.data.tradingStartTime ?? null,
      tradingEndTime: parsed.data.tradingEndTime ?? null,
      forceCloseTime: parsed.data.forceCloseTime ?? null,
      maxDailyLossPts: parsed.data.maxDailyLossPts ?? null,
      maxDailyProfitPts: parsed.data.maxDailyProfitPts ?? null,
      breakEvenPts: parsed.data.breakEvenPts ?? null,
      cancelPendingAfterBars: parsed.data.cancelPendingAfterBars ?? null,
    })
    .where(eq(botConfigTable.id, params.data.id))
    .returning();

  res.json(UpdateSymbolConfigResponse.parse(rowToSymbolConfig(updated)));
});

// ---------------------------------------------------------------------------
// NEW: DELETE /bot/configs/:id — delete a configuration by numeric ID
// ---------------------------------------------------------------------------
router.delete("/bot/configs/:id", async (req, res): Promise<void> => {
  const params = DeleteSymbolConfigByIdParams.safeParse({ id: req.params.id });
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const existing = await db
    .select({ id: botConfigTable.id })
    .from(botConfigTable)
    .where(eq(botConfigTable.id, params.data.id))
    .limit(1);

  if (existing.length === 0) {
    res.status(404).json({ error: `Config id '${params.data.id}' not found` });
    return;
  }

  await db
    .delete(botConfigTable)
    .where(eq(botConfigTable.id, params.data.id));

  res.status(204).send();
});

// ---------------------------------------------------------------------------
// LEGACY: GET /bot/config — returns first symbol config (backward-compat)
// ---------------------------------------------------------------------------
router.get("/bot/config", async (req, res): Promise<void> => {
  await ensureDefaultConfig();
  const [config] = await db
    .select()
    .from(botConfigTable)
    .orderBy(asc(botConfigTable.symbol))
    .limit(1);

  res.json(GetBotConfigResponse.parse(rowToSymbolConfig(config)));
});

// ---------------------------------------------------------------------------
// LEGACY: PUT /bot/config — updates first symbol config (backward-compat)
// ---------------------------------------------------------------------------
router.put("/bot/config", async (req, res): Promise<void> => {
  const parsed = UpdateBotConfigBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  await ensureDefaultConfig();
  const [existing] = await db
    .select()
    .from(botConfigTable)
    .orderBy(asc(botConfigTable.symbol))
    .limit(1);

  const [updated] = await db
    .update(botConfigTable)
    .set({
      symbol: parsed.data.symbol,
      strategyName: parsed.data.strategyName ?? existing.strategyName,
      strategyParams: parsed.data.strategyParams ?? existing.strategyParams,
      lotSize: parsed.data.lotSize,
      ma200Period: parsed.data.ma200Period,
      entryOffset: parsed.data.entryOffset,
      stopLoss: parsed.data.stopLoss,
      partial1Percent: parsed.data.partial1Percent,
      partial1Points: parsed.data.partial1Points,
      partial2Percent: parsed.data.partial2Percent,
      partial2Points: parsed.data.partial2Points,
      partial3Points: parsed.data.partial3Points,
      maxOpenTrades: parsed.data.maxOpenTrades,
      maxDailyStops: parsed.data.maxDailyStops,
      timeframeMinutes: parsed.data.timeframeMinutes,
      tradingStartTime: parsed.data.tradingStartTime ?? null,
      tradingEndTime: parsed.data.tradingEndTime ?? null,
      forceCloseTime: parsed.data.forceCloseTime ?? null,
      maxDailyLossPts: parsed.data.maxDailyLossPts ?? null,
      maxDailyProfitPts: parsed.data.maxDailyProfitPts ?? null,
      breakEvenPts: parsed.data.breakEvenPts ?? null,
      cancelPendingAfterBars: parsed.data.cancelPendingAfterBars ?? null,
    })
    .where(eq(botConfigTable.id, existing.id))
    .returning();

  res.json(UpdateBotConfigResponse.parse(rowToSymbolConfig(updated)));
});

// ---------------------------------------------------------------------------
// GET /bot/status
// ---------------------------------------------------------------------------
router.get("/bot/status", async (req, res): Promise<void> => {
  await ensureDefaultStatus();
  await ensureDefaultConfig();

  const [status] = await db.select().from(botStatusTable).orderBy(botStatusTable.id).limit(1);
  const [config] = await db.select().from(botConfigTable).orderBy(asc(botConfigTable.symbol)).limit(1);

  const openTradesCount = await db
    .select({ count: count() })
    .from(tradesTable)
    .where(eq(tradesTable.status, "open"));

  const openCount = openTradesCount[0]?.count ?? 0;
  const pendingCount = await db
    .select({ count: count() })
    .from(tradesTable)
    .where(eq(tradesTable.status, "pending"));

  const activeCount = openCount + (pendingCount[0]?.count ?? 0);
  const isBlocked =
    status.dailyStops >= config.maxDailyStops ||
    activeCount >= config.maxOpenTrades;

  let blockReason: string | null = null;
  if (status.dailyStops >= config.maxDailyStops) {
    blockReason = `${status.dailyStops} stops atingidos hoje (máx: ${config.maxDailyStops})`;
  } else if (activeCount >= config.maxOpenTrades) {
    blockReason = `${activeCount} operações ativas (máx: ${config.maxOpenTrades})`;
  }

  res.json(GetBotStatusResponse.parse({
    isRunning: status.isRunning,
    openTrades: Number(openCount),
    dailyStops: status.dailyStops,
    isBlocked,
    blockReason: status.blockReason ?? blockReason,
    lastSignalAt: status.lastSignalAt?.toISOString() ?? null,
    currentMa200: status.currentMa200 ?? null,
    currentPrice: status.currentPrice ?? null,
  }));
});

// ---------------------------------------------------------------------------
// GET /bot/trades
// ---------------------------------------------------------------------------
router.get("/bot/trades", async (req, res): Promise<void> => {
  const parsed = ListTradesQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const limit = parsed.data.limit ?? 50;
  const status = parsed.data.status;

  const trades = status
    ? await db
        .select()
        .from(tradesTable)
        .where(eq(tradesTable.status, status))
        .orderBy(desc(tradesTable.createdAt))
        .limit(limit)
    : await db
        .select()
        .from(tradesTable)
        .orderBy(desc(tradesTable.createdAt))
        .limit(limit);

  res.json(ListTradesResponse.parse(
    trades.map((t) => ({
      id: t.id,
      symbol: t.symbol,
      strategyName: t.strategyName ?? null,
      direction: t.direction,
      entryPrice: t.entryPrice ?? null,
      orderPrice: t.orderPrice,
      stopLoss: t.stopLoss,
      ma200AtEntry: t.ma200AtEntry,
      lotSize: t.lotSize,
      status: t.status,
      partial1Closed: t.partial1Closed,
      partial2Closed: t.partial2Closed,
      closedAt: t.closedAt?.toISOString() ?? null,
      openedAt: t.openedAt?.toISOString() ?? null,
      createdAt: t.createdAt.toISOString(),
      profitLoss: t.profitLoss ?? null,
      closeReason: t.closeReason ?? null,
    }))
  ));
});

// ---------------------------------------------------------------------------
// GET /bot/trades/:id
// ---------------------------------------------------------------------------
router.get("/bot/trades/:id", async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const params = GetTradeParams.safeParse({ id: parseInt(raw, 10) });
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [trade] = await db
    .select()
    .from(tradesTable)
    .where(eq(tradesTable.id, params.data.id));

  if (!trade) {
    res.status(404).json({ error: "Trade not found" });
    return;
  }

  res.json(GetTradeResponse.parse({
    id: trade.id,
    symbol: trade.symbol,
    strategyName: trade.strategyName ?? null,
    direction: trade.direction,
    entryPrice: trade.entryPrice ?? null,
    orderPrice: trade.orderPrice,
    stopLoss: trade.stopLoss,
    ma200AtEntry: trade.ma200AtEntry,
    lotSize: trade.lotSize,
    status: trade.status,
    partial1Closed: trade.partial1Closed,
    partial2Closed: trade.partial2Closed,
    closedAt: trade.closedAt?.toISOString() ?? null,
    openedAt: trade.openedAt?.toISOString() ?? null,
    createdAt: trade.createdAt.toISOString(),
    profitLoss: trade.profitLoss ?? null,
    closeReason: trade.closeReason ?? null,
  }));
});

// ---------------------------------------------------------------------------
// GET /bot/summary
// ---------------------------------------------------------------------------
router.get("/bot/summary", async (req, res): Promise<void> => {
  const allTrades = await db.select().from(tradesTable);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const todayTrades = allTrades.filter(
    (t) => t.createdAt >= today
  );

  const closed = allTrades.filter((t) => t.status === "closed");
  const open = allTrades.filter((t) => t.status === "open");
  const cancelled = allTrades.filter((t) => t.status === "cancelled");
  const wins = closed.filter((t) => (t.profitLoss ?? 0) > 0);
  const losses = closed.filter((t) => (t.profitLoss ?? 0) <= 0);

  const totalPnl = closed.reduce((acc, t) => acc + (t.profitLoss ?? 0), 0);
  const todayPnl = todayTrades
    .filter((t) => t.status === "closed")
    .reduce((acc, t) => acc + (t.profitLoss ?? 0), 0);

  const todayLosses = todayTrades.filter(
    (t) => t.status === "closed" && (t.profitLoss ?? 0) <= 0
  );

  const [statusRow] = await db.select().from(botStatusTable).limit(1);

  res.json(GetBotSummaryResponse.parse({
    totalTrades: allTrades.length,
    openTrades: open.length,
    closedTrades: closed.length,
    cancelledTrades: cancelled.length,
    totalWins: wins.length,
    totalLosses: losses.length,
    winRate: closed.length > 0 ? (wins.length / closed.length) * 100 : 0,
    totalPnl,
    todayPnl,
    todayTrades: todayTrades.length,
    dailyStops: statusRow?.dailyStops ?? todayLosses.length,
  }));
});

// ---------------------------------------------------------------------------
// GET /bot/settings — global settings (discord toggle + webhook status)
// ---------------------------------------------------------------------------
async function ensureDefaultSettings() {
  const existing = await db.select().from(globalSettingsTable).limit(1);
  if (existing.length === 0) {
    await db.insert(globalSettingsTable).values({ discordEnabled: false });
  }
}

router.get("/bot/settings", async (req, res): Promise<void> => {
  await ensureDefaultSettings();
  const [row] = await db.select().from(globalSettingsTable).limit(1);
  res.json(GetBotSettingsResponse.parse({
    discordEnabled: row.discordEnabled,
    discordWebhookConfigured: !!process.env.DISCORD_WEBHOOK_URL,
  }));
});

// ---------------------------------------------------------------------------
// PATCH /bot/settings — update discord_enabled toggle
// ---------------------------------------------------------------------------
router.patch("/bot/settings", async (req, res): Promise<void> => {
  const parsed = UpdateBotSettingsBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  await ensureDefaultSettings();
  const [row] = await db.select().from(globalSettingsTable).limit(1);

  await db
    .update(globalSettingsTable)
    .set({ discordEnabled: parsed.data.discordEnabled })
    .where(eq(globalSettingsTable.id, row.id));

  res.json(GetBotSettingsResponse.parse({
    discordEnabled: parsed.data.discordEnabled,
    discordWebhookConfigured: !!process.env.DISCORD_WEBHOOK_URL,
  }));
});

export default router;
