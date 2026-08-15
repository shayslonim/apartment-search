import { requeueApartmentAnalysis } from "@/db/apartments";
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
  const id = idFrom(payload);
  if (!id) return Response.json({ error: "id_required" }, { status: 400 });

  const accepted = await requeueApartmentAnalysis(id);
  return accepted
    ? Response.json({ accepted: true, status: "pending" })
    : Response.json({ error: "listing_not_requeueable" }, { status: 409 });
}

function idFrom(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const id = (value as Record<string, unknown>).id;
  if (typeof id !== "string") return null;
  const normalized = id.trim();
  return normalized && normalized.length <= 500 ? normalized : null;
}
