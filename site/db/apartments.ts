import { env } from "cloudflare:workers";
import type { ApartmentPost, ScoreResult, StoredApartment } from "@/lib/types";

let schemaPromise: Promise<void> | null = null;

export type ApartmentStats = {
  total: number;
  strong: number;
  review: number;
  averageScore: number;
};

export async function ensureApartmentSchema(): Promise<void> {
  schemaPromise ??= initializeSchema();
  return schemaPromise;
}

export async function insertApartment(
  id: string,
  post: ApartmentPost,
  score: ScoreResult,
): Promise<boolean> {
  await ensureApartmentSchema();
  const result = await database()
    .prepare(
      `INSERT OR IGNORE INTO apartment_posts (
        id, source, group_name, author, post_url, body, posted_at,
        score, decision, summary, price_ils, listing_type, location_signal,
        shelter_signal, positives, negatives, unknowns, telegram_status, raw_payload
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
    .bind(
      id,
      post.source,
      post.groupName,
      post.author,
      post.url,
      post.text,
      post.postedAt,
      score.score,
      score.decision,
      score.summary,
      score.priceIls,
      score.listingType,
      score.locationSignal,
      score.shelterSignal,
      JSON.stringify(score.positives),
      JSON.stringify(score.negatives),
      JSON.stringify(score.unknowns),
      score.decision === "send" ? "pending" : "not_applicable",
      JSON.stringify(post.raw),
    )
    .run();
  return Number(result.meta.changes ?? 0) > 0;
}

export async function updateTelegramStatus(id: string, status: string): Promise<void> {
  await database()
    .prepare("UPDATE apartment_posts SET telegram_status = ? WHERE id = ?")
    .bind(status, id)
    .run();
}

export async function listApartments(limit = 100): Promise<StoredApartment[]> {
  await ensureApartmentSchema();
  const result = await database()
    .prepare(
      `SELECT id, source, group_name, author, post_url, body, posted_at,
        received_at, score, decision, summary, price_ils, listing_type,
        location_signal, shelter_signal, positives, negatives, unknowns,
        telegram_status
      FROM apartment_posts
      ORDER BY received_at DESC, score DESC
      LIMIT ?`,
    )
    .bind(limit)
    .all<StoredApartment>();
  return result.results;
}

export async function apartmentStats(): Promise<ApartmentStats> {
  await ensureApartmentSchema();
  const row = await database()
    .prepare(
      `SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN decision = 'send' THEN 1 ELSE 0 END) AS strong,
        SUM(CASE WHEN decision = 'review' THEN 1 ELSE 0 END) AS review,
        COALESCE(AVG(score), 0) AS average_score
      FROM apartment_posts`,
    )
    .first<{
      total: number;
      strong: number | null;
      review: number | null;
      average_score: number;
    }>();

  return {
    total: Number(row?.total ?? 0),
    strong: Number(row?.strong ?? 0),
    review: Number(row?.review ?? 0),
    averageScore: Math.round(Number(row?.average_score ?? 0)),
  };
}

function database(): D1Database {
  const binding = (env as unknown as { DB?: D1Database }).DB;
  if (!binding) throw new Error("Cloudflare D1 binding DB is unavailable");
  return binding;
}

async function initializeSchema(): Promise<void> {
  const db = database();
  await db.batch([
    db.prepare(
      `CREATE TABLE IF NOT EXISTS apartment_posts (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        group_name TEXT,
        author TEXT,
        post_url TEXT,
        body TEXT NOT NULL,
        posted_at TEXT,
        received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        score INTEGER NOT NULL,
        decision TEXT NOT NULL,
        summary TEXT NOT NULL,
        price_ils INTEGER,
        listing_type TEXT NOT NULL,
        location_signal TEXT NOT NULL,
        shelter_signal TEXT NOT NULL,
        positives TEXT NOT NULL,
        negatives TEXT NOT NULL,
        unknowns TEXT NOT NULL,
        telegram_status TEXT NOT NULL DEFAULT 'disabled',
        raw_payload TEXT NOT NULL
      )`,
    ),
    db.prepare(
      "CREATE INDEX IF NOT EXISTS idx_apartment_posts_received_at " +
        "ON apartment_posts(received_at DESC)",
    ),
    db.prepare(
      "CREATE INDEX IF NOT EXISTS idx_apartment_posts_decision_score " +
        "ON apartment_posts(decision, score DESC)",
    ),
  ]);
}
