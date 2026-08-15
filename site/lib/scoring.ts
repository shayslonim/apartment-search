import type { ApartmentPost, Decision, ScoreResult } from "./types";

const MONTEFIORE_TERMS = ["montefiore", "מונטיפיורי"];
const SARONA_TERMS = ["sarona", "שרונה"];
const WORK_TERMS = ["hahaskala", "ha-haskala", "haskala", "ההשכלה", "השכלה 3"];
const NEARBY_TERMS = [
  "menachem begin", "מנחם בגין", "hashmonaim", "החשמונאים",
  "hamasger", "המסגר", "yigal alon", "יגאל אלון",
  "nachalat yitzhak", "נחלת יצחק",
];
const QUALITY_POSITIVE_TERMS = [
  "renovated", "maintained", "bright", "clean", "pleasant", "balcony",
  "elevator", "furnished", "משופצת", "שמורה", "מוארת", "נקייה",
  "נקי", "נעימה", "מרפסת", "מעלית", "מרוהטת",
];
const QUALITY_NEGATIVE_TERMS = [
  "neglected", "run down", "mold", "damp", "broken", "needs renovation",
  "מוזנחת", "עובש", "טחב", "רטיבות", "שבורה", "דורשת שיפוץ",
];
const CITY_LIFE_TERMS = [
  "cafe", "cafes", "restaurant", "restaurants", "bar", "bars", "nightlife",
  "בתי קפה", "בית קפה", "מסעדות", "ברים", "חיי לילה",
];
const SHARED_TERMS = ["roommate", "roommates", "shared", "שותף", "שותפה", "שותפים"];
const SOLO_TERMS = ["studio", "דירה לבד", "סטודיו", "יחידת דיור"];
const PRICE_CONTEXT_TERMS = [
  "₪", "שח", "ש\"ח", "nis", "ils", "rent", "price", "מחיר", "שכירות", "שכר דירה",
];

export function scorePost(post: ApartmentPost): ScoreResult {
  const text = normalize(post.text);
  const positives: string[] = [];
  const negatives: string[] = [];
  const unknowns: string[] = [];
  let score = 0;

  const location = locationScore(text);
  score += location.score;
  if (location.signal === "unknown") {
    unknowns.push("Location is not specific enough");
  } else {
    positives.push(location.signal);
  }

  const commute = commuteScore(text);
  score += commute.score;
  if (commute.signal) {
    positives.push(commute.signal);
  } else {
    unknowns.push("Distance to HaHaskala 3, Tel Aviv is unknown");
  }

  let qualityScore = 8;
  const hasPositiveQuality = containsAny(text, QUALITY_POSITIVE_TERMS);
  const hasNegativeQuality = containsAny(text, QUALITY_NEGATIVE_TERMS);
  if (hasPositiveQuality) {
    qualityScore += 10;
    positives.push("Maintained, renovated, bright, or pleasant condition");
  }
  if (hasNegativeQuality) {
    qualityScore -= 18;
    negatives.push("Condition warning: neglected, damp, mold, or needs renovation");
  }
  if (!hasPositiveQuality && !hasNegativeQuality) {
    unknowns.push("Apartment condition is unclear");
  }
  score += clamp(qualityScore, -15, 20);

  const listingType = listingTypeFrom(text);
  const priceIls = parsePriceIls(post.text);
  score += applyPriceScore(priceIls, listingType, positives, negatives, unknowns);

  const shelter = shelterScore(text, positives, negatives, unknowns);
  score += shelter.score;

  const moveIn = moveInScore(text);
  score += moveIn.score;
  if (moveIn.signal) {
    positives.push(moveIn.signal);
  } else {
    unknowns.push("Move-in date is not clearly September or October 2026");
  }

  if (containsAny(text, CITY_LIFE_TERMS)) {
    score += 5;
    positives.push("Nearby cafes, restaurants, bars, or city life");
  }

  score = clamp(score, 0, 100);
  const decision: Decision = score >= 70 ? "send" : score >= 55 ? "review" : "reject";
  const priceLabel = priceIls ? `${priceIls} ILS` : "price unknown";

  return {
    score,
    decision,
    summary:
      `${decision.toUpperCase()} score ${score}: ${location.signal}, ` +
      `${priceLabel}, shelter=${shelter.signal}`,
    positives: unique(positives),
    negatives: unique(negatives),
    unknowns: unique(unknowns),
    priceIls,
    listingType,
    locationSignal: location.signal,
    shelterSignal: shelter.signal,
  };
}

export function parsePriceIls(text: string): number | null {
  const candidates: Array<{ context: number; value: number }> = [];

  for (const match of text.matchAll(/(?<!\w)(\d{1,2}(?:[.,]\d{1,2})?)\s*[kK]\b/g)) {
    const value = Math.trunc(Number(match[1].replace(",", ".")) * 1000);
    if (value >= 1500 && value <= 12000) candidates.push({ context: 2, value });
  }

  const pattern = /(?<!\d)(\d{1,2}[,.]\d{3}|\d{4,5})(?!\d)/g;
  for (const match of text.matchAll(pattern)) {
    const value = Number(match[1].replace(/[,.]/g, ""));
    if (value < 1500 || value > 12000 || (value >= 1900 && value <= 2099)) continue;
    const start = Math.max(0, (match.index ?? 0) - 24);
    const end = (match.index ?? 0) + match[0].length + 24;
    const context = containsAny(normalize(text.slice(start, end)), PRICE_CONTEXT_TERMS) ? 2 : 1;
    candidates.push({ context, value });
  }

  candidates.sort((left, right) => right.context - left.context || left.value - right.value);
  return candidates[0]?.value ?? null;
}

function locationScore(text: string): { score: number; signal: string } {
  if (containsAny(text, MONTEFIORE_TERMS)) return { score: 35, signal: "Montefiore" };
  if (containsAny(text, SARONA_TERMS)) return { score: 30, signal: "Sarona" };
  if (containsAny(text, WORK_TERMS)) return { score: 28, signal: "HaHaskala 3 / work area" };
  if (containsAny(text, NEARBY_TERMS)) {
    return { score: 22, signal: "Nearby central-east Tel Aviv signal" };
  }
  return {
    score: text.includes("tel aviv") || text.includes("תל אביב") ? 8 : 0,
    signal: "unknown",
  };
}

function commuteScore(text: string): { score: number; signal: string | null } {
  const walking = ["walk", "walking", "הליכה", "דקות", "minute", "minutes"];
  const short = ["15", "10", "12", "short", "near", "קרוב", "קצר"];
  const transit = ["light rail", "bus", "רכבת קלה", "אוטובוס"];
  if (containsAny(text, WORK_TERMS)) {
    return { score: 15, signal: "Direct HaHaskala/work-area mention" };
  }
  if (containsAny(text, SARONA_TERMS) && containsAny(text, walking)) {
    return { score: 13, signal: "Walking-distance Sarona signal" };
  }
  if (containsAny(text, walking) && containsAny(text, short)) {
    return { score: 10, signal: "Short walking-distance signal" };
  }
  if (containsAny(text, transit) && containsAny(text, short)) {
    return { score: 7, signal: "Short public-transit signal" };
  }
  return { score: 0, signal: null };
}

function applyPriceScore(
  price: number | null,
  type: "shared" | "solo" | "unknown",
  positives: string[],
  negatives: string[],
  unknowns: string[],
): number {
  if (price === null) {
    unknowns.push("Price is missing");
    return 3;
  }
  if (type === "shared") {
    if (price <= 4000) {
      positives.push("Shared-room price is within target budget");
      return 15;
    }
    if (price <= 4500) {
      positives.push("Shared-room price is slightly over target");
      return 10;
    }
    negatives.push("Shared-room price is over stretch budget");
    return 2;
  }
  if (type === "solo") {
    if (price <= 4500) {
      positives.push("Solo-apartment price is within target budget");
      return 15;
    }
    negatives.push("Solo-apartment price is over target budget");
    return 2;
  }
  if (price <= 4000) {
    positives.push("Price is within shared-apartment target");
    return 12;
  }
  if (price <= 4500) {
    positives.push("Price is within stretch/solo range");
    return 8;
  }
  negatives.push("Price appears high for the target search");
  return 2;
}

function shelterScore(
  text: string,
  positives: string[],
  negatives: string[],
  unknowns: string[],
): { score: number; signal: string } {
  const noMamad = /(אין|ללא)\s*(ממד|ממ"ד)|no\s+mamad/.test(text);
  const noShelter = /(אין|ללא)\s*(מקלט|מרחב מוגן)|no\s+shelter/.test(text);
  const hasMamad = /\b(mamad|safe room)\b|ממד|ממ"ד/.test(text) && !noMamad;
  const hasShelter = /\bshelter\b|מקלט|מרחב מוגן/.test(text) && !noShelter;

  if (hasMamad) {
    positives.push("Mamad inside the apartment");
    return { score: 10, signal: "mamad" };
  }
  if (hasShelter) {
    positives.push("Shelter in building or nearby protected space");
    return { score: 6, signal: "shelter" };
  }
  if (noMamad && noShelter) {
    negatives.push("Explicitly says there is no Mamad and no shelter");
    return { score: -8, signal: "none" };
  }
  if (noMamad) {
    negatives.push("No Mamad stated");
    unknowns.push("Shelter availability is unclear");
    return { score: -2, signal: "no_mamad_unknown_shelter" };
  }
  unknowns.push("Mamad/shelter information is missing");
  return { score: 2, signal: "unknown" };
}

function moveInScore(text: string): { score: number; signal: string | null } {
  const september = [
    "september 2026", "sep 2026", "sept 2026", "09/2026", "9/2026",
    "ספטמבר 2026", "ספטמבר",
  ];
  const october = ["october 2026", "oct 2026", "10/2026", "אוקטובר 2026", "אוקטובר"];
  if (containsAny(text, september)) {
    return { score: 5, signal: "Move-in matches September 2026" };
  }
  if (containsAny(text, october)) {
    return { score: 5, signal: "Move-in matches October 2026" };
  }
  return { score: 0, signal: null };
}

function listingTypeFrom(text: string): "shared" | "solo" | "unknown" {
  if (containsAny(text, SHARED_TERMS)) return "shared";
  if (containsAny(text, SOLO_TERMS)) return "solo";
  return "unknown";
}

function normalize(value: string): string {
  return value.toLocaleLowerCase().replace(/\s+/g, " ");
}

function containsAny(text: string, terms: string[]): boolean {
  return terms.some((term) => text.includes(term.toLocaleLowerCase()));
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
