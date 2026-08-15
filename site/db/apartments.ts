import { env } from "cloudflare:workers";
import type {
  AnalysisJob,
  AnalysisResult,
  ApartmentPost,
  StoredApartment,
} from "@/lib/types";

let schemaPromise: Promise<void> | null = null;

export type ApartmentStats = {
  total: number;
  recommended: number;
  justOkay: number;
  notReally: number;
  queued: number;
  failed: number;
};

export async function ensureApartmentSchema(): Promise<void> {
  schemaPromise ??= initializeSchema();
  return schemaPromise;
}

export async function insertPendingApartment(
  id: string,
  post: ApartmentPost,
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
      0,
      "not_really",
      "Awaiting local AI analysis",
      null,
      "unknown",
      "unknown",
      "unknown",
      "[]",
      "[]",
      "[]",
      "not_applicable",
      JSON.stringify(post.raw),
    )
    .run();
  return Number(result.meta.changes ?? 0) > 0;
}

export async function claimApartmentForAnalysis(workerId: string): Promise<AnalysisJob | null> {
  await ensureApartmentSchema();
  const db = database();
  const claimId = crypto.randomUUID();
  const claimed = await db
    .prepare(
      `UPDATE apartment_posts
       SET analysis_status = 'processing',
           analysis_attempts = analysis_attempts + 1,
           analysis_claim_id = ?,
           analysis_worker = ?,
           analysis_claimed_at = CURRENT_TIMESTAMP,
           analysis_error = NULL
       WHERE id = (
         SELECT id FROM apartment_posts
         WHERE analysis_attempts < 5
           AND (
             analysis_status = 'pending'
             OR (
               analysis_status = 'processing'
               AND analysis_claimed_at <= datetime('now', '-30 minutes')
             )
           )
         ORDER BY received_at ASC
         LIMIT 1
       )`,
    )
    .bind(claimId, workerId)
    .run();

  if (Number(claimed.meta.changes ?? 0) === 0) return null;

  const row = await db
    .prepare(
      `SELECT id, analysis_claim_id AS claim_id, source, group_name, author,
              post_url, body, posted_at, received_at, raw_payload
       FROM apartment_posts
       WHERE analysis_claim_id = ? AND analysis_status = 'processing'
       LIMIT 1`,
    )
    .bind(claimId)
    .first<AnalysisJob>();
  return row ?? null;
}

export async function completeApartmentAnalysis(
  id: string,
  claimId: string,
  result: AnalysisResult,
  rawResult: unknown,
): Promise<boolean> {
  await ensureApartmentSchema();
  const updated = await database()
    .prepare(
      `UPDATE apartment_posts
       SET score = ?, decision = ?, summary = ?, price_ils = ?, listing_type = ?,
           location_signal = ?, shelter_signal = ?, positives = ?, negatives = ?,
           unknowns = ?, telegram_status = ?, analysis_status = 'complete',
           analyzed_at = CURRENT_TIMESTAMP, analysis_model = ?, location_text = ?,
           geocoded_address = ?, latitude = ?, longitude = ?, location_confidence = ?,
           condition_signal = ?, move_in_signal = ?, walk_to_work_minutes = ?,
           walk_to_work_meters = ?, walk_to_sarona_minutes = ?,
           walk_to_sarona_meters = ?, analysis_payload = ?, analysis_error = NULL,
           analysis_claim_id = NULL, analysis_worker = NULL
       WHERE id = ? AND analysis_claim_id = ? AND analysis_status = 'processing'`,
    )
    .bind(
      result.score,
      result.category,
      result.summary,
      result.priceIls,
      result.listingType,
      result.locationSignal,
      result.shelterSignal,
      JSON.stringify(result.positives),
      JSON.stringify(result.concerns),
      JSON.stringify(result.unknowns),
      result.category === "recommended" ? "pending" : "not_applicable",
      result.model,
      result.locationText,
      result.geocodedAddress,
      result.latitude,
      result.longitude,
      result.locationConfidence,
      result.conditionSignal,
      result.moveInSignal,
      result.walkToWorkMinutes,
      result.walkToWorkMeters,
      result.walkToSaronaMinutes,
      result.walkToSaronaMeters,
      JSON.stringify(rawResult),
      id,
      claimId,
    )
    .run();
  return Number(updated.meta.changes ?? 0) > 0;
}

export async function failApartmentAnalysis(
  id: string,
  claimId: string,
  error: string,
): Promise<boolean> {
  await ensureApartmentSchema();
  const updated = await database()
    .prepare(
      `UPDATE apartment_posts
       SET analysis_status = CASE WHEN analysis_attempts >= 5 THEN 'failed' ELSE 'pending' END,
           analysis_error = ?, analysis_claim_id = NULL, analysis_worker = NULL
       WHERE id = ? AND analysis_claim_id = ? AND analysis_status = 'processing'`,
    )
    .bind(error.slice(0, 2000), id, claimId)
    .run();
  return Number(updated.meta.changes ?? 0) > 0;
}

export async function requeueApartmentAnalysis(id: string): Promise<boolean> {
  await ensureApartmentSchema();
  const updated = await database()
    .prepare(
      `UPDATE apartment_posts
       SET analysis_status = 'pending', analysis_attempts = 0,
           analysis_claim_id = NULL, analysis_worker = NULL,
           analysis_claimed_at = NULL, analysis_error = NULL
       WHERE id = ? AND analysis_status IN ('complete', 'failed')`,
    )
    .bind(id)
    .run();
  return Number(updated.meta.changes ?? 0) > 0;
}

export async function apartmentPostById(id: string): Promise<ApartmentPost | null> {
  await ensureApartmentSchema();
  const row = await database()
    .prepare(
      `SELECT source, group_name, author, post_url, body, posted_at, raw_payload
       FROM apartment_posts WHERE id = ? LIMIT 1`,
    )
    .bind(id)
    .first<{
      source: string;
      group_name: string | null;
      author: string | null;
      post_url: string | null;
      body: string;
      posted_at: string | null;
      raw_payload: string;
    }>();
  if (!row) return null;
  return {
    source: row.source,
    groupName: row.group_name,
    author: row.author,
    url: row.post_url,
    text: row.body,
    postedAt: row.posted_at,
    raw: parseObject(row.raw_payload),
  };
}

export async function updateTelegramStatus(id: string, status: string): Promise<void> {
  await database()
    .prepare("UPDATE apartment_posts SET telegram_status = ? WHERE id = ?")
    .bind(status, id)
    .run();
}

export async function listApartments(): Promise<StoredApartment[]> {
  await ensureApartmentSchema();
  const result = await database()
    .prepare(
      `SELECT id, source, group_name, author, post_url, body, posted_at,
        received_at, score, decision, summary, price_ils, listing_type,
        location_signal, shelter_signal, positives, negatives, unknowns,
        telegram_status, analysis_status, analysis_model, location_text,
        geocoded_address, latitude, longitude, location_confidence,
        condition_signal, move_in_signal, walk_to_work_minutes,
        walk_to_work_meters, walk_to_sarona_minutes, walk_to_sarona_meters
       FROM apartment_posts
       WHERE analysis_status = 'complete'
       ORDER BY CASE decision
         WHEN 'recommended' THEN 0
         WHEN 'just_okay' THEN 1
         ELSE 2
       END, score DESC, received_at DESC`,
    )
    .all<StoredApartment>();
  return result.results;
}

export async function apartmentStats(): Promise<ApartmentStats> {
  await ensureApartmentSchema();
  const row = await database()
    .prepare(
      `SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN analysis_status = 'complete' AND decision = 'recommended' THEN 1 ELSE 0 END) AS recommended,
        SUM(CASE WHEN analysis_status = 'complete' AND decision = 'just_okay' THEN 1 ELSE 0 END) AS just_okay,
        SUM(CASE WHEN analysis_status = 'complete' AND decision = 'not_really' THEN 1 ELSE 0 END) AS not_really,
        SUM(CASE WHEN analysis_status IN ('pending', 'processing') THEN 1 ELSE 0 END) AS queued,
        SUM(CASE WHEN analysis_status = 'failed' THEN 1 ELSE 0 END) AS failed
       FROM apartment_posts`,
    )
    .first<Record<string, number | null>>();

  return {
    total: Number(row?.total ?? 0),
    recommended: Number(row?.recommended ?? 0),
    justOkay: Number(row?.just_okay ?? 0),
    notReally: Number(row?.not_really ?? 0),
    queued: Number(row?.queued ?? 0),
    failed: Number(row?.failed ?? 0),
  };
}

function database(): D1Database {
  const binding = (env as unknown as { DB?: D1Database }).DB;
  if (!binding) throw new Error("Cloudflare D1 binding DB is unavailable");
  return binding;
}

async function initializeSchema(): Promise<void> {
  const db = database();
  await db.prepare(
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
      raw_payload TEXT NOT NULL,
      analysis_status TEXT NOT NULL DEFAULT 'pending',
      analysis_attempts INTEGER NOT NULL DEFAULT 0,
      analysis_claim_id TEXT,
      analysis_worker TEXT,
      analysis_claimed_at TEXT,
      analyzed_at TEXT,
      analysis_model TEXT,
      location_text TEXT,
      geocoded_address TEXT,
      latitude REAL,
      longitude REAL,
      location_confidence TEXT,
      condition_signal TEXT,
      move_in_signal TEXT,
      walk_to_work_minutes INTEGER,
      walk_to_work_meters INTEGER,
      walk_to_sarona_minutes INTEGER,
      walk_to_sarona_meters INTEGER,
      analysis_payload TEXT,
      analysis_error TEXT
    )`,
  ).run();
  await ensureAnalysisColumns(db);
  await db.batch([
    db.prepare(
      "CREATE INDEX IF NOT EXISTS idx_apartment_posts_received_at " +
        "ON apartment_posts(received_at DESC)",
    ),
    db.prepare(
      "CREATE INDEX IF NOT EXISTS idx_apartment_posts_decision_score " +
        "ON apartment_posts(decision, score DESC)",
    ),
    db.prepare(
      "CREATE INDEX IF NOT EXISTS idx_apartment_posts_analysis_queue " +
        "ON apartment_posts(analysis_status, received_at)",
    ),
  ]);
}

async function ensureAnalysisColumns(db: D1Database): Promise<void> {
  const existing = await db
    .prepare("PRAGMA table_info(apartment_posts)")
    .all<{ name: string }>();
  const names = new Set(existing.results.map((column) => column.name));
  const definitions: Record<string, string> = {
    analysis_status: "TEXT NOT NULL DEFAULT 'pending'",
    analysis_attempts: "INTEGER NOT NULL DEFAULT 0",
    analysis_claim_id: "TEXT",
    analysis_worker: "TEXT",
    analysis_claimed_at: "TEXT",
    analyzed_at: "TEXT",
    analysis_model: "TEXT",
    location_text: "TEXT",
    geocoded_address: "TEXT",
    latitude: "REAL",
    longitude: "REAL",
    location_confidence: "TEXT",
    condition_signal: "TEXT",
    move_in_signal: "TEXT",
    walk_to_work_minutes: "INTEGER",
    walk_to_work_meters: "INTEGER",
    walk_to_sarona_minutes: "INTEGER",
    walk_to_sarona_meters: "INTEGER",
    analysis_payload: "TEXT",
    analysis_error: "TEXT",
  };
  const missing = Object.entries(definitions).filter(([name]) => !names.has(name));
  if (missing.length) {
    await db.batch(
      missing.map(([name, definition]) =>
        db.prepare(`ALTER TABLE apartment_posts ADD COLUMN ${name} ${definition}`),
      ),
    );
  }
}

function parseObject(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}
