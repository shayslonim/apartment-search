import { cookies } from "next/headers";
import {
  DASHBOARD_COOKIE,
  dashboardSession,
  secureEqual,
} from "@/lib/auth";
import { requireEnvironmentValue } from "@/lib/env";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  let supplied = "";
  try {
    const body = (await request.json()) as { token?: unknown };
    supplied = typeof body.token === "string" ? body.token : "";
  } catch {
    return Response.json({ error: "invalid_request" }, { status: 400 });
  }

  const expected = requireEnvironmentValue("DASHBOARD_SECRET");
  if (!(await secureEqual(supplied, expected))) {
    return Response.json({ error: "invalid_access_key" }, { status: 401 });
  }

  const jar = await cookies();
  jar.set(DASHBOARD_COOKIE, await dashboardSession(expected), {
    httpOnly: true,
    sameSite: "strict",
    secure: new URL(request.url).protocol === "https:",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return Response.json({ status: "ok" });
}

export async function DELETE(): Promise<Response> {
  const jar = await cookies();
  jar.delete(DASHBOARD_COOKIE);
  return Response.json({ status: "ok" });
}
