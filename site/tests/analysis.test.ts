import assert from "node:assert/strict";
import test from "node:test";
import { AnalysisResultError, parseAnalysisResult } from "../lib/analysis";

test("accepts a complete local analyzer result", () => {
  const result = parseAnalysisResult({
    category: "recommended",
    score: 88,
    summary: "Excellent Montefiore match with a short walk to work.",
    positives: ["Montefiore", "Within budget"],
    concerns: [],
    unknowns: ["Shelter details are missing"],
    price_ils: 3900,
    listing_type: "shared",
    location_signal: "Montefiore",
    location_text: "Montefiore, Tel Aviv",
    geocoded_address: "Montefiore, Tel Aviv-Yafo, Israel",
    latitude: 32.063,
    longitude: 34.779,
    location_confidence: "medium",
    shelter_signal: "unknown",
    condition_signal: "good",
    move_in_signal: "match",
    walk_to_work_minutes: 13,
    walk_to_work_meters: 980,
    walk_to_sarona_minutes: 11,
    walk_to_sarona_meters: 820,
    model: "qwen3:8b",
  });

  assert.equal(result.category, "recommended");
  assert.equal(result.walkToWorkMinutes, 13);
  assert.equal(result.walkToSaronaMeters, 820);
});

test("rejects categories outside the three dashboard outcomes", () => {
  assert.throws(
    () => parseAnalysisResult({ category: "send" }),
    AnalysisResultError,
  );
});
