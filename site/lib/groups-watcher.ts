import type { ApartmentPost } from "./types";

export class GroupsWatcherPayloadError extends Error {}

export function postsFromPayload(payload: unknown): ApartmentPost[] {
  if (!isRecord(payload)) {
    throw new GroupsWatcherPayloadError("Payload must be a JSON object");
  }

  let candidates: unknown[];
  if ("data" in payload) {
    candidates = [payload.data];
  } else if ("posts" in payload && Array.isArray(payload.posts)) {
    candidates = payload.posts;
  } else {
    throw new GroupsWatcherPayloadError(
      "Payload must contain a data object or posts list",
    );
  }

  if (candidates.length === 0) {
    throw new GroupsWatcherPayloadError("Payload does not contain any posts");
  }

  return candidates.map((candidate, index) => normalizePost(candidate, index));
}

export async function postId(post: ApartmentPost): Promise<string> {
  const identity = post.url || post.text.trim();
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(identity),
  );
  const hex = Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `${post.source}:${hex}`;
}

function normalizePost(value: unknown, index: number): ApartmentPost {
  if (!isRecord(value)) {
    throw new GroupsWatcherPayloadError(`Post ${index} must be an object`);
  }

  const text = firstString(value.body, value.post_text, value.text);
  if (!text) {
    throw new GroupsWatcherPayloadError(`Post ${index} is missing body`);
  }

  const groupName = optionalString(value.group_name);
  const groupId = optionalString(value.group_id);
  return {
    source: `groups-watcher:${groupName || groupId || "unknown-group"}`,
    text,
    url: optionalString(value.post_url),
    postedAt: postedAt(value.timestamp, value.time_posted, value.posted_unix),
    author: firstString(value.poster_name, value.profile_name),
    groupName,
    raw: value,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const normalized = String(value).trim();
  return normalized || null;
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    const normalized = optionalString(value);
    if (normalized) return normalized;
  }
  return null;
}

function postedAt(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) {
      const milliseconds = value < 10_000_000_000 ? value * 1000 : value;
      return new Date(milliseconds).toISOString();
    }
    const normalized = optionalString(value);
    if (normalized) return normalized;
  }
  return null;
}
