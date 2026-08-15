import { ensureApartmentSchema } from "@/db/apartments";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    await ensureApartmentSchema();
    return Response.json({ status: "ok", storage: "ready" });
  } catch {
    return Response.json({ status: "degraded", storage: "unavailable" }, { status: 503 });
  }
}
