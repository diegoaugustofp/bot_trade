import { pgTable, serial, text, real, integer, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const tradesTable = pgTable("trades", {
  id: serial("id").primaryKey(),
  symbol: text("symbol").notNull(),
  strategyName: text("strategy_name"),
  direction: text("direction").notNull(), // BUY | SELL
  orderPrice: real("order_price").notNull(),
  entryPrice: real("entry_price"),
  stopLoss: real("stop_loss").notNull(),
  ma200AtEntry: real("ma200_at_entry").notNull(),
  lotSize: real("lot_size").notNull(),
  status: text("status").notNull().default("pending"), // pending | open | closed | cancelled
  partial1Closed: boolean("partial1_closed").notNull().default(false),
  partial2Closed: boolean("partial2_closed").notNull().default(false),
  profitLoss: real("profit_loss"),
  closeReason: text("close_reason"),
  openedAt: timestamp("opened_at", { withTimezone: true }),
  closedAt: timestamp("closed_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const insertTradeSchema = createInsertSchema(tradesTable).omit({ id: true, createdAt: true });
export type InsertTrade = z.infer<typeof insertTradeSchema>;
export type Trade = typeof tradesTable.$inferSelect;
