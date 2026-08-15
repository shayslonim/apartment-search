import assert from "node:assert/strict";
import test from "node:test";
import { parsePriceIls, scorePost } from "../lib/scoring";
import type { ApartmentPost } from "../lib/types";

test("ignores the move-in year while parsing rent", () => {
  assert.equal(
    parsePriceIls("Available September 2026. Rent is 3,800 ILS."),
    3800,
  );
});

test("ranks a strong Montefiore listing as a send candidate", () => {
  const result = scorePost(
    post(
      "Montefiore room with roommates, renovated and bright, 3800 ILS, " +
        "September 2026, Mamad inside, cafes nearby, 10 minutes walking.",
    ),
  );

  assert.equal(result.decision, "send");
  assert.ok(result.score >= 70);
  assert.equal(result.priceIls, 3800);
  assert.equal(result.shelterSignal, "mamad");
});

test("treats no Mamad and no shelter as a major negative", () => {
  const result = scorePost(
    post("Tel Aviv apartment, old condition, 5200 ILS. No mamad and no shelter."),
  );

  assert.equal(result.decision, "reject");
  assert.equal(result.shelterSignal, "none");
  assert.ok(result.negatives.some((value) => value.includes("no Mamad and no shelter")));
});

function post(text: string): ApartmentPost {
  return {
    source: "test",
    text,
    url: null,
    postedAt: null,
    author: null,
    groupName: null,
    raw: {},
  };
}
