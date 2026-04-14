import { pgTable, serial, boolean, timestamp } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const globalSettingsTable = pgTable("global_settings", {
  id: serial("id").primaryKey(),
  discordEnabled: boolean("discord_enabled").notNull().default(false),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow().$onUpdate(() => new Date()),
});

export const insertGlobalSettingsSchema = createInsertSchema(globalSettingsTable).omit({ id: true, updatedAt: true });
export type InsertGlobalSettings = z.infer<typeof insertGlobalSettingsSchema>;
export type GlobalSettings = typeof globalSettingsTable.$inferSelect;
