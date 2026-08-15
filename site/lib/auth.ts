const encoder = new TextEncoder();

export const DASHBOARD_COOKIE = "apartment_search_session";

export function webhookToken(request: Request): string {
  const url = new URL(request.url);
  const queryToken = url.searchParams.get("token");
  const headerToken = request.headers.get("x-webhook-secret");
  const authorization = request.headers.get("authorization");
  const bearer = authorization?.startsWith("Bearer ")
    ? authorization.slice(7)
    : null;
  return headerToken || bearer || queryToken || "";
}

export async function secureEqual(left: string, right: string): Promise<boolean> {
  const [leftHash, rightHash] = await Promise.all([digest(left), digest(right)]);
  let difference = 0;
  for (let index = 0; index < leftHash.length; index += 1) {
    difference |= leftHash[index] ^ rightHash[index];
  }
  return difference === 0;
}

export async function dashboardSession(secret: string): Promise<string> {
  return hex(await digest(`apartment-search-dashboard:${secret}`));
}

export async function validDashboardSession(
  session: string | undefined,
  secret: string,
): Promise<boolean> {
  if (!session) return false;
  return secureEqual(session, await dashboardSession(secret));
}

async function digest(value: string): Promise<Uint8Array> {
  const result = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return new Uint8Array(result);
}

function hex(value: Uint8Array): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
