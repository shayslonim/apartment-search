import {
  ensureApartmentSchema,
  insertPendingApartment,
} from "@/db/apartments";
import { secureEqual, webhookToken } from "@/lib/auth";
import { requireEnvironmentValue } from "@/lib/env";
import {
  GroupsWatcherPayloadError,
  postId,
  postsFromPayload,
} from "@/lib/groups-watcher";

export const dynamic = "force-dynamic";
const MAX_REQUEST_BYTES = 2 * 1024 * 1024;

export async function POST(request: Request): Promise<Response> {
  let expectedSecret: string;
  try {
    expectedSecret = requireEnvironmentValue("GROUPS_WATCHER_WEBHOOK_SECRET");
  } catch {
    return Response.json({ error: "receiver_not_configured" }, { status: 503 });
  }

  if (!(await secureEqual(webhookToken(request), expectedSecret))) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const declaredLength = Number(request.headers.get("content-length") || "0");
  if (declaredLength > MAX_REQUEST_BYTES) {
    return Response.json({ error: "payload_too_large" }, { status: 413 });
  }

  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) {
    return Response.json({ error: "payload_too_large" }, { status: 413 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  try {
    const posts = postsFromPayload(payload);
    await ensureApartmentSchema();
    let processed = 0;
    let skippedSeen = 0;

    for (const post of posts) {
      const id = await postId(post);
      const inserted = await insertPendingApartment(id, post);
      if (!inserted) {
        skippedSeen += 1;
        continue;
      }

      processed += 1;
    }

    return Response.json({
      event: "groups_watcher_delivery",
      accepted: posts.length,
      processed,
      skipped_seen: skippedSeen,
      queued_for_analysis: processed,
    });
  } catch (error) {
    if (error instanceof GroupsWatcherPayloadError) {
      return Response.json(
        { error: "invalid_payload", detail: error.message },
        { status: 400 },
      );
    }
    console.error("Groups Watcher processing failed", error);
    return Response.json({ error: "processing_failed" }, { status: 500 });
  }
}
