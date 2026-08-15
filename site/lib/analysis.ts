import type { AnalysisResult, Category } from "./types";

export class AnalysisResultError extends Error {}

const CATEGORIES: Category[] = ["recommended", "just_okay", "not_really"];

export function parseAnalysisResult(value: unknown): AnalysisResult {
  if (!isRecord(value)) throw new AnalysisResultError("result must be an object");

  return {
    score: integer(value.score, "score", 0, 100),
    category: enumValue(value.category, "category", CATEGORIES),
    summary: requiredString(value.summary, "summary", 1200),
    positives: stringList(value.positives, "positives"),
    concerns: stringList(value.concerns, "concerns"),
    unknowns: stringList(value.unknowns, "unknowns"),
    priceIls: optionalInteger(value.price_ils, "price_ils", 0, 100_000),
    listingType: enumValue(value.listing_type, "listing_type", ["shared", "solo", "unknown"]),
    locationSignal: requiredString(value.location_signal, "location_signal", 300),
    locationText: optionalString(value.location_text, "location_text", 500),
    geocodedAddress: optionalString(value.geocoded_address, "geocoded_address", 500),
    latitude: optionalNumber(value.latitude, "latitude", -90, 90),
    longitude: optionalNumber(value.longitude, "longitude", -180, 180),
    locationConfidence: enumValue(value.location_confidence, "location_confidence", [
      "high",
      "medium",
      "low",
      "unknown",
    ]),
    shelterSignal: enumValue(value.shelter_signal, "shelter_signal", [
      "mamad",
      "shelter",
      "none",
      "unknown",
    ]),
    conditionSignal: enumValue(value.condition_signal, "condition_signal", [
      "excellent",
      "good",
      "acceptable",
      "poor",
      "unknown",
    ]),
    moveInSignal: enumValue(value.move_in_signal, "move_in_signal", [
      "match",
      "mismatch",
      "flexible",
      "unknown",
    ]),
    walkToWorkMinutes: optionalInteger(
      value.walk_to_work_minutes,
      "walk_to_work_minutes",
      0,
      600,
    ),
    walkToWorkMeters: optionalInteger(
      value.walk_to_work_meters,
      "walk_to_work_meters",
      0,
      100_000,
    ),
    walkToSaronaMinutes: optionalInteger(
      value.walk_to_sarona_minutes,
      "walk_to_sarona_minutes",
      0,
      600,
    ),
    walkToSaronaMeters: optionalInteger(
      value.walk_to_sarona_meters,
      "walk_to_sarona_meters",
      0,
      100_000,
    ),
    model: requiredString(value.model, "model", 200),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, name: string, maximum: number): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new AnalysisResultError(`${name} must be a non-empty string`);
  }
  const normalized = value.trim();
  if (normalized.length > maximum) {
    throw new AnalysisResultError(`${name} is too long`);
  }
  return normalized;
}

function optionalString(value: unknown, name: string, maximum: number): string | null {
  if (value === null || value === undefined || value === "") return null;
  return requiredString(value, name, maximum);
}

function integer(
  value: unknown,
  name: string,
  minimum: number,
  maximum: number,
): number {
  if (!Number.isInteger(value) || Number(value) < minimum || Number(value) > maximum) {
    throw new AnalysisResultError(`${name} must be an integer from ${minimum} to ${maximum}`);
  }
  return Number(value);
}

function optionalInteger(
  value: unknown,
  name: string,
  minimum: number,
  maximum: number,
): number | null {
  if (value === null || value === undefined) return null;
  return integer(value, name, minimum, maximum);
}

function optionalNumber(
  value: unknown,
  name: string,
  minimum: number,
  maximum: number,
): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || value > maximum) {
    throw new AnalysisResultError(`${name} must be a number from ${minimum} to ${maximum}`);
  }
  return value;
}

function enumValue<T extends string>(value: unknown, name: string, values: readonly T[]): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new AnalysisResultError(`${name} must be one of: ${values.join(", ")}`);
  }
  return value as T;
}

function stringList(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || value.length > 12) {
    throw new AnalysisResultError(`${name} must be a list with at most 12 items`);
  }
  return value.map((item, index) => requiredString(item, `${name}[${index}]`, 500));
}
