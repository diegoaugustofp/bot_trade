import { pgTable, serial, text, real, integer, timestamp, jsonb, uniqueIndex } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const botConfigTable = pgTable(
  "bot_config",
  {
    id: serial("id").primaryKey(),
    symbol: text("symbol").notNull().default("WINM25"),
    strategyName: text("strategy_name").notNull().default("ma200_rejection"),
    strategyParams: jsonb("strategy_params").notNull().default({}).$type<Record<string, unknown>>(),
    lotSize: real("lot_size").notNull().default(1.0),
    ma200Period: integer("ma200_period").notNull().default(200),
    entryOffset: real("entry_offset").notNull().default(10.0),
    stopLoss: real("stop_loss").notNull().default(20.0),
    partial1Percent: real("partial1_percent").notNull().default(60.0),
    partial1Points: real("partial1_points").notNull().default(20.0),
    partial2Percent: real("partial2_percent").notNull().default(20.0),
    partial2Points: real("partial2_points").notNull().default(50.0),
    partial3Points: real("partial3_points").notNull().default(100.0),
    maxOpenTrades: integer("max_open_trades").notNull().default(3),
    maxDailyStops: integer("max_daily_stops").notNull().default(2),
    timeframeMinutes: integer("timeframe_minutes").notNull().default(5),
    tradingStartTime: text("trading_start_time"),
    tradingEndTime: text("trading_end_time"),
    forceCloseTime: text("force_close_time"),
    maxDailyLossPts: real("max_daily_loss_pts"),
    maxDailyProfitPts: real("max_daily_profit_pts"),
    breakEvenPts: real("break_even_pts"),
    cancelPendingAfterBars: integer("cancel_pending_after_bars"),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
  },
  (table) => [
    uniqueIndex("bot_config_symbol_strategy_unique").on(table.symbol, table.strategyName),
  ],
);

export const insertBotConfigSchema = createInsertSchema(botConfigTable).omit({ id: true, updatedAt: true });
export type InsertBotConfig = z.infer<typeof insertBotConfigSchema>;
export type BotConfig = typeof botConfigTable.$inferSelect;
