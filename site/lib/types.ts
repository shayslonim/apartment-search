export type Decision = "send" | "review" | "reject";

export type ApartmentPost = {
  source: string;
  text: string;
  url: string | null;
  postedAt: string | null;
  author: string | null;
  groupName: string | null;
  raw: Record<string, unknown>;
};

export type ScoreResult = {
  score: number;
  decision: Decision;
  summary: string;
  positives: string[];
  negatives: string[];
  unknowns: string[];
  priceIls: number | null;
  listingType: "shared" | "solo" | "unknown";
  locationSignal: string;
  shelterSignal: string;
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
  decision: Decision;
  summary: string;
  price_ils: number | null;
  listing_type: string;
  location_signal: string;
  shelter_signal: string;
  positives: string;
  negatives: string;
  unknowns: string;
  telegram_status: string;
};
