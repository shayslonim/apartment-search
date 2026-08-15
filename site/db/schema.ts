import { sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

export const apartmentPosts = sqliteTable(
  "apartment_posts",
  {
    id: text("id").primaryKey(),
    source: text("source").notNull(),
    groupName: text("group_name"),
    author: text("author"),
    postUrl: text("post_url"),
    body: text("body").notNull(),
    postedAt: text("posted_at"),
    receivedAt: text("received_at").notNull().default(sql`CURRENT_TIMESTAMP`),
    score: integer("score").notNull(),
    decision: text("decision").notNull(),
    summary: text("summary").notNull(),
    priceIls: integer("price_ils"),
    listingType: text("listing_type").notNull(),
    locationSignal: text("location_signal").notNull(),
    shelterSignal: text("shelter_signal").notNull(),
    positives: text("positives").notNull(),
    negatives: text("negatives").notNull(),
    unknowns: text("unknowns").notNull(),
    telegramStatus: text("telegram_status").notNull().default("disabled"),
    rawPayload: text("raw_payload").notNull(),
  },
  (table) => [
    index("idx_apartment_posts_received_at").on(table.receivedAt),
    index("idx_apartment_posts_decision_score").on(
      table.decision,
      table.score,
    ),
  ],
);
