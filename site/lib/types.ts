export type Category = "recommended" | "just_okay" | "not_really";
export type AnalysisStatus = "pending" | "processing" | "complete" | "failed";

export type ApartmentPost = {
  source: string;
  text: string;
  url: string | null;
  postedAt: string | null;
  author: string | null;
  groupName: string | null;
  raw: Record<string, unknown>;
};

export type AnalysisResult = {
  score: number;
  category: Category;
  summary: string;
  positives: string[];
  concerns: string[];
  unknowns: string[];
  priceIls: number | null;
  listingType: "shared" | "solo" | "unknown";
  locationSignal: string;
  locationText: string | null;
  geocodedAddress: string | null;
  latitude: number | null;
  longitude: number | null;
  locationConfidence: "high" | "medium" | "low" | "unknown";
  shelterSignal: "mamad" | "shelter" | "none" | "unknown";
  conditionSignal: "excellent" | "good" | "acceptable" | "poor" | "unknown";
  moveInSignal: "match" | "mismatch" | "flexible" | "unknown";
  walkToWorkMinutes: number | null;
  walkToWorkMeters: number | null;
  walkToSaronaMinutes: number | null;
  walkToSaronaMeters: number | null;
  model: string;
};

export type AnalysisJob = {
  id: string;
  claim_id: string;
  source: string;
  group_name: string | null;
  author: string | null;
  post_url: string | null;
  body: string;
  posted_at: string | null;
  received_at: string;
  raw_payload: string;
};

export type StoredApartment = {
  id: string;
  source: string;
  group_name: string | null;
  author: string | null;
  post_url: string | null;
  body: string;
  posted_at: string | null;
  received_at: string;
  score: number;
  decision: Category;
  summary: string;
  price_ils: number | null;
  listing_type: string;
  location_signal: string;
  shelter_signal: string;
  positives: string;
  negatives: string;
  unknowns: string;
  telegram_status: string;
  analysis_status: AnalysisStatus;
  analysis_model: string | null;
  location_text: string | null;
  geocoded_address: string | null;
  latitude: number | null;
  longitude: number | null;
  location_confidence: string | null;
  condition_signal: string | null;
  move_in_signal: string | null;
  walk_to_work_minutes: number | null;
  walk_to_work_meters: number | null;
  walk_to_sarona_minutes: number | null;
  walk_to_sarona_meters: number | null;
};
