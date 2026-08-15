import { claimApartmentForAnalysis } from "@/db/apartments";
import { analyzerAuthorization } from "@/lib/analyzer-auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const authorization = await analyzerAuthorization(request);
  if (authorization === "unconfigured") {
    return Response.json({ error: "analyzer_not_configured" }, { status: 503 });
  }
  if (authorization === "unauthorized") {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }
  const workerId = workerIdFrom(payload);
  if (!workerId) {
    return Response.json({ error: "worker_id_required" }, { status: 400 });
  }

  const job = await claimApartmentForAnalysis(workerId);
  if (!job) return new Response(null, { status: 204 });
  return Response.json({ job });
}

function workerIdFrom(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const workerId = (value as Record<string, unknown>).worker_id;
  if (typeof workerId !== "string") return null;
  const normalized = workerId.trim();
  return normalized && normalized.length <= 120 ? normalized : null;
}
