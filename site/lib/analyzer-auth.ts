import { secureEqual, webhookToken } from "./auth";
import { environmentValue } from "./env";

export async function analyzerAuthorization(
  request: Request,
): Promise<"ok" | "unconfigured" | "unauthorized"> {
  const expected = environmentValue("LOCAL_ANALYZER_SECRET");
  if (!expected) return "unconfigured";
  return (await secureEqual(webhookToken(request), expected)) ? "ok" : "unauthorized";
}
