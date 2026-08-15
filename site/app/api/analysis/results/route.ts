import {
  apartmentPostById,
  completeApartmentAnalysis,
  failApartmentAnalysis,
  updateTelegramStatus,
} from "@/db/apartments";
import { AnalysisResultError, parseAnalysisResult } from "@/lib/analysis";
import { analyzerAuthorization } from "@/lib/analyzer-auth";
import { sendTelegramMatch } from "@/lib/telegram";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const authorization = await analyzerAuthorization(request);
  if (authorization === "unconfigured") {
    return Response.json({ error: "analyzer_not_configured" }, { status: 503 });
  }
  if (authorization === "unauthorized") {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  let payload: Record<string, unknown>;
  try {
    const parsed = await request.json();
    if (!isRecord(parsed)) throw new Error("not an object");
    payload = parsed;
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  const id = shortString(payload.id, 500);
  const claimId = shortString(payload.claim_id, 200);
  if (!id || !claimId) {
    return Response.json({ error: "id_and_claim_id_required" }, { status: 400 });
  }

  const reportedError = shortString(payload.error, 2000);
  if (reportedError) {
    const accepted = await failApartmentAnalysis(id, claimId, reportedError);
    return accepted
      ? Response.json({ accepted: true, status: "retry_queued" })
      : Response.json({ error: "claim_not_active" }, { status: 409 });
  }

  try {
    const result = parseAnalysisResult(payload.result);
    const accepted = await completeApartmentAnalysis(id, claimId, result, payload.result);
    if (!accepted) {
      return Response.json({ error: "claim_not_active" }, { status: 409 });
    }

    let telegramStatus = "not_applicable";
    if (result.category === "recommended") {
      const post = await apartmentPostById(id);
      telegramStatus = post ? await sendTelegramMatch(post, result) : "error";
      await updateTelegramStatus(id, telegramStatus);
    }
    return Response.json({ accepted: true, category: result.category, telegram_status: telegramStatus });
  } catch (error) {
    if (error instanceof AnalysisResultError) {
      return Response.json(
        { error: "invalid_analysis_result", detail: error.message },
        { status: 400 },
      );
    }
    console.error("Analysis result processing failed", error);
    return Response.json({ error: "processing_failed" }, { status: 500 });
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function shortString(value: unknown, maximum: number): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized && normalized.length <= maximum ? normalized : null;
}
