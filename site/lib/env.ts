import { env } from "cloudflare:workers";

export function environmentValue(name: string): string | null {
  const value = (env as unknown as Record<string, unknown>)[name];
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function requireEnvironmentValue(name: string): string {
  const value = environmentValue(name);
  if (!value) throw new Error(`${name} is not configured`);
  return value;
}
