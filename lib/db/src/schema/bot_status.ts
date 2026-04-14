import { pgTable, serial, boolean, integer, real, timestamp, text } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const botStatusTable = pgTable("bot_status", {
  id: serial("id").primaryKey(),
  isRunning: boolean("is_running").notNull().default(false),
  dailyStops: integer("daily_stops").notNull().default(0),
  currentMa200: real("current_ma200"),
  currentPrice: real("current_price"),
  lastSignalAt: timestamp("last_signal_at", { withTimezone: true }),
  blockReason: text("block_reason"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertBotStatusSchema = createInsertSchema(botStatusTable).omit({ id: true, updatedAt: true });
export type InsertBotStatus = z.infer<typeof insertBotStatusSchema>;
export type BotStatus = typeof botStatusTable.$inferSelect;
