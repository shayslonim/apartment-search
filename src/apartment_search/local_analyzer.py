"""Local Ollama analysis with geocoding and pedestrian routing."""

from __future__ import annotations

import json
import math
import sqlite3
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import certifi

WORK_ADDRESS = "3 HaHaskala, Tel Aviv"
SARONA_ADDRESS = "Sarona Market, Tel Aviv"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

SEARCH_GUIDELINES = """
Evaluate apartments for this specific personal search:
- Give the strongest preference to Montefiore or anywhere within comfortable
  walking distance of Sarona.
- The work address is HaHaskala 3, Tel Aviv. Ideally the apartment is within
  about 15 minutes walking of work or Sarona, or has very short public transit.
- Move-in should be September or October 2026.
- For a shared apartment, target up to 3,500-4,000 ILS per room. A slight
  overage is acceptable only for an exceptional apartment.
- For an apartment alone, target roughly 4,000-4,500 ILS, and only when it is
  reasonably spacious and in decent condition.
- The apartment should be maintained, pleasant, and livable. Strongly
  downgrade visibly or explicitly neglected and run-down apartments.
- A Mamad inside the apartment is excellent. A shelter in the building is
  acceptable. Missing protection information is an uncertainty, not an
  automatic rejection. Explicitly no Mamad and no accessible shelter is a
  major negative.
- Prefer pleasant urban surroundings. Nearby cafes, restaurants, bars, and
  city life are a strong bonus.
- Existing-roommate and shared-apartment listings are relevant.

Priority order:
1. Montefiore or walking distance to Sarona.
2. Actual walking distance to HaHaskala 3.
3. Apartment condition and livability.
4. Price.
5. Mamad or shelter.

Categories:
- recommended: a strong actionable match worth contacting promptly.
- just_okay: plausible but has compromises or important missing information.
- not_really: materially misses the search or has major negatives.
""".strip()

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "location_query": {"type": "string"},
        "location_text": {"type": "string"},
        "location_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "unknown"],
        },
        "listing_type": {
            "type": "string",
            "enum": ["shared", "solo", "unknown"],
        },
        "price_ils": {"type": "integer", "minimum": 0, "maximum": 100000},
        "move_in_signal": {
            "type": "string",
            "enum": ["match", "mismatch", "flexible", "unknown"],
        },
        "condition_signal": {
            "type": "string",
            "enum": ["excellent", "good", "acceptable", "poor", "unknown"],
        },
        "shelter_signal": {
            "type": "string",
            "enum": ["mamad", "shelter", "none", "unknown"],
        },
        "facts": {"type": "array", "items": {"type": "string"}},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "location_query",
        "location_text",
        "location_confidence",
        "listing_type",
        "price_ils",
        "move_in_signal",
        "condition_signal",
        "shelter_signal",
        "facts",
        "concerns",
        "unknowns",
    ],
    "additionalProperties": False,
}

SHELTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "shelter_signal": {
            "type": "string",
            "enum": ["mamad", "shelter", "none", "unknown"],
        }
    },
    "required": ["shelter_signal"],
    "additionalProperties": False,
}

VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": ["recommended", "just_okay", "not_really"],
        },
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "location_signal": {"type": "string"},
        "shelter_signal": {
            "type": "string",
            "enum": ["mamad", "shelter", "none", "unknown"],
        },
        "positives": {"type": "array", "items": {"type": "string"}},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "unknowns": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "category",
        "score",
        "summary",
        "location_signal",
        "shelter_signal",
        "positives",
        "concerns",
        "unknowns",
    ],
    "additionalProperties": False,
}


class AnalysisError(RuntimeError):
    """Raised when a listing cannot be analyzed safely."""


@dataclass(frozen=True)
class Place:
    label: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WalkingRoute:
    minutes: int
    meters: int


class StructuredModel(Protocol):
    model: str

    def generate(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class Geocoder(Protocol):
    def geocode(self, query: str) -> Place | None: ...


class PedestrianRouter(Protocol):
    def route(self, origin: Place, destination: Place) -> WalkingRoute | None: ...


class JsonCache:
    """Persistent cache for public map-service responses."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS json_cache (
                key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                stored_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def get(self, key: str) -> Any | None:
        row = self.connection.execute(
            "SELECT payload FROM json_cache WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: Any) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO json_cache (key, payload) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class OllamaModel:
    """Structured-output client for a local Ollama server."""

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 180,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response = request_json(
            f"{self.base_url}/api/chat",
            method="POST",
            payload={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1},
            },
            timeout=self.timeout,
        )
        try:
            content = response["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AnalysisError("Ollama returned an invalid structured response") from exc
        if not isinstance(parsed, dict):
            raise AnalysisError("Ollama response must be a JSON object")
        return parsed


class NominatimGeocoder:
    """Low-volume, cached OpenStreetMap Nominatim geocoder."""

    def __init__(
        self,
        cache: JsonCache,
        base_url: str = "https://nominatim.openstreetmap.org/search",
        minimum_interval_seconds: float = 15.0,
    ) -> None:
        self.cache = cache
        self.base_url = base_url
        self.minimum_interval_seconds = minimum_interval_seconds
        self.last_request_at = 0.0

    def geocode(self, query: str) -> Place | None:
        normalized = canonicalize_location_query(query)
        if not normalized:
            return None
        if "tel aviv" not in normalized.lower() and "תל אביב" not in normalized:
            normalized = f"{normalized}, Tel Aviv-Yafo, Israel"
        cache_key = f"geocode:{normalized.casefold()}"
        cached = self.cache.get(cache_key)
        if cached is None:
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < self.minimum_interval_seconds:
                time.sleep(self.minimum_interval_seconds - elapsed)
            url = self.base_url + "?" + urllib.parse.urlencode(
                {
                    "q": normalized,
                    "format": "jsonv2",
                    "limit": 5,
                    "countrycodes": "il",
                    "addressdetails": 1,
                }
            )
            cached = request_json(url, headers=map_headers(), timeout=30)
            self.last_request_at = time.monotonic()
            self.cache.put(cache_key, cached)
        if not isinstance(cached, list):
            raise AnalysisError("Geocoder returned an invalid response")
        candidates = [item for item in cached if isinstance(item, dict)]
        tel_aviv = [item for item in candidates if is_tel_aviv_candidate(item)]
        selected = tel_aviv[0] if tel_aviv else None
        if not selected:
            return None
        try:
            return Place(
                label=str(selected["display_name"]),
                latitude=float(selected["lat"]),
                longitude=float(selected["lon"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AnalysisError("Geocoder result is missing coordinates") from exc


class OsrmFootRouter:
    """Cached pedestrian routes using the FOSSGIS OpenStreetMap service."""

    def __init__(
        self,
        cache: JsonCache,
        base_url: str = (
            "https://routing.openstreetmap.de/routed-foot/route/v1/driving"
        ),
        minimum_interval_seconds: float = 1.1,
    ) -> None:
        self.cache = cache
        self.base_url = base_url.rstrip("/")
        self.minimum_interval_seconds = minimum_interval_seconds
        self.last_request_at = 0.0

    def route(self, origin: Place, destination: Place) -> WalkingRoute | None:
        cache_key = (
            "walk:"
            f"{origin.latitude:.6f},{origin.longitude:.6f}:"
            f"{destination.latitude:.6f},{destination.longitude:.6f}"
        )
        cached = self.cache.get(cache_key)
        if cached is None:
            elapsed = time.monotonic() - self.last_request_at
            if elapsed < self.minimum_interval_seconds:
                time.sleep(self.minimum_interval_seconds - elapsed)
            coordinates = (
                f"{origin.longitude:.6f},{origin.latitude:.6f};"
                f"{destination.longitude:.6f},{destination.latitude:.6f}"
            )
            url = f"{self.base_url}/{coordinates}?overview=false&steps=false"
            cached = request_json(
                url,
                headers=map_headers(),
                timeout=45,
            )
            self.last_request_at = time.monotonic()
            self.cache.put(cache_key, cached)
        try:
            route = cached["routes"][0]
            seconds = float(route["duration"])
            meters = float(route["distance"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AnalysisError("Walking router returned an invalid response") from exc
        return WalkingRoute(
            minutes=max(1, math.ceil(seconds / 60)),
            meters=max(1, round(meters)),
        )


class ApartmentAnalyzer:
    """Two-pass LLM analysis grounded with route-service facts."""

    def __init__(
        self,
        model: StructuredModel,
        geocoder: Geocoder,
        router: PedestrianRouter,
    ) -> None:
        self.model = model
        self.geocoder = geocoder
        self.router = router

    def analyze(self, job: dict[str, Any]) -> dict[str, Any]:
        body = required_text(job.get("body"), "job.body")
        analysis_body = normalize_listing_text(body)
        extraction = self.model.generate(
            system=(
                "Extract only facts supported by the Facebook apartment post. "
                "Do not make the final recommendation yet. Interpret Hebrew and "
                "English naturally. Set move_in_signal=match when September 2026 or "
                "October 2026 is stated; mismatch for a clearly different fixed date; "
                "flexible for an open or negotiable date; otherwise unknown. Classify "
                "condition from explicit descriptions: excellent for clearly renovated "
                "and exceptional condition; good for maintained, bright, clean, or "
                "pleasant; acceptable for ordinary but livable condition; poor for "
                "neglected, mold, damp, broken, or needs renovation; unknown only when "
                "the post gives no condition evidence. "
                "Classify listing_type as shared for a room or roommates and solo for "
                "a whole apartment or studio. Distinguish an in-apartment Mamad from "
                "a building shelter, and never infer protection when it is absent. "
                "Recognize Mamad even when its Hebrew acronym uses straight quotes, "
                "Hebrew punctuation, or no punctuation. Recognize miklat as a shelter. "
                "Hebrew Mamad spellings include \u05de\u05de\u05d3 and \u05de\u05de\"\u05d3; Hebrew shelter is "
                "\u05de\u05e7\u05dc\u05d8. When the post explicitly contains one of these terms, "
                "shelter_signal must not be unknown. "
                "Use 0 for an unknown price. Create a geocoding query only when the "
                "post gives a street, neighborhood, landmark, or clear area. Do not "
                "put a fact in unknowns or concerns when the post explicitly states it."
            ),
            user=f"Facebook post:\n{analysis_body}",
            schema=EXTRACTION_SCHEMA,
        )
        extraction = validate_extraction(extraction)
        shelter = self.model.generate(
            system=(
                "Classify only the apartment's protection information from the post. "
                "Return mamad for an in-apartment Mamad, including \u05de\u05de\u05d3 or \u05de\u05de\"\u05d3. "
                "Return shelter for a building/public shelter, including \u05de\u05e7\u05dc\u05d8. Return "
                "none only when the post explicitly says neither is accessible. Return "
                "unknown when protection is not mentioned. Do not infer facts."
            ),
            user=f"Facebook post:\n{analysis_body}",
            schema=SHELTER_SCHEMA,
        )
        extraction["shelter_signal"] = enum_text(
            shelter.get("shelter_signal"),
            "shelter_signal",
            {"mamad", "shelter", "none", "unknown"},
        )

        listing_place = self.geocoder.geocode(extraction["location_query"])
        work_place = self.geocoder.geocode(WORK_ADDRESS) if listing_place else None
        sarona_place = self.geocoder.geocode(SARONA_ADDRESS) if listing_place else None
        work_route = (
            self.router.route(listing_place, work_place)
            if listing_place and work_place
            else None
        )
        sarona_route = (
            self.router.route(listing_place, sarona_place)
            if listing_place and sarona_place
            else None
        )

        route_facts = {
            "geocoded_address": listing_place.label if listing_place else None,
            "walk_to_hahaskala_3": route_dict(work_route),
            "walk_to_sarona_market": route_dict(sarona_route),
        }
        verdict = self.model.generate(
            system=(
                "You are the final apartment evaluator. Follow the personal search "
                "guidelines exactly. Treat route-service values as verified facts. "
                "Verified walking times override assumptions based on neighborhood "
                "names. Do not recommend a listing when both verified walks are far "
                "beyond the target unless the post explicitly establishes very short "
                "public transit and the rest of the listing is exceptional. "
                "Review extracted fields against the complete post and correct any "
                "inconsistency. In particular, shelter_signal must be mamad when the "
                "post explicitly says \u05de\u05de\u05d3 or \u05de\u05de\"\u05d3, and shelter when it says "
                "\u05de\u05e7\u05dc\u05d8. Never invent missing details. Consider the complete post and return "
                "one of exactly three categories. location_signal must be a concise, "
                "human-readable location or area label, such as 'Montefiore' or "
                "'Florentin, 28 min from work'; never return only 'match', 'unknown', "
                "or another abstract verdict.\n\n" + SEARCH_GUIDELINES
            ),
            user=(
                f"Facebook post:\n{analysis_body}\n\n"
                f"Extracted facts:\n{json.dumps(extraction, ensure_ascii=False)}\n\n"
                f"Verified map facts:\n{json.dumps(route_facts, ensure_ascii=False)}"
            ),
            schema=VERDICT_SCHEMA,
        )
        verdict = validate_verdict(verdict)

        return {
            "category": verdict["category"],
            "score": verdict["score"],
            "summary": verdict["summary"],
            "location_signal": verdict["location_signal"],
            "positives": verdict["positives"],
            "concerns": unique_strings(extraction["concerns"] + verdict["concerns"]),
            "unknowns": unique_strings(extraction["unknowns"] + verdict["unknowns"]),
            "price_ils": extraction["price_ils"] or None,
            "listing_type": extraction["listing_type"],
            "location_text": extraction["location_text"] or None,
            "geocoded_address": listing_place.label if listing_place else None,
            "latitude": listing_place.latitude if listing_place else None,
            "longitude": listing_place.longitude if listing_place else None,
            "location_confidence": extraction["location_confidence"],
            "shelter_signal": extraction["shelter_signal"],
            "condition_signal": extraction["condition_signal"],
            "move_in_signal": extraction["move_in_signal"],
            "walk_to_work_minutes": work_route.minutes if work_route else None,
            "walk_to_work_meters": work_route.meters if work_route else None,
            "walk_to_sarona_minutes": sarona_route.minutes if sarona_route else None,
            "walk_to_sarona_meters": sarona_route.meters if sarona_route else None,
            "model": self.model.model,
        }


def request_json(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    request_headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=SSL_CONTEXT,
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise AnalysisError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"Request failed for {url}: {exc}") from exc


def map_headers() -> dict[str, str]:
    return {
        "User-Agent": "ApartmentSearch/0.2 (personal apartment search)",
        "Referer": "https://apartment-search.shaysks.chatgpt.site/",
    }


def is_tel_aviv_candidate(item: dict[str, Any]) -> bool:
    address = item.get("address")
    if not isinstance(address, dict):
        return False
    municipality_fields = (
        address.get("city"),
        address.get("town"),
        address.get("village"),
        address.get("municipality"),
    )
    return any(is_tel_aviv_name(value) for value in municipality_fields)


def canonicalize_location_query(query: str) -> str:
    normalized = query.strip()
    folded = normalized.casefold()
    latin_key = "".join(character for character in folded if character.isalnum())

    montefiore_aliases = ("montefiore", "montefiori", "montifiore", "montifiori")
    if any(alias in latin_key for alias in montefiore_aliases) or "\u05de\u05d5\u05e0\u05d8\u05d9\u05e4\u05d9\u05d5\u05e8\u05d9" in folded:
        return "Montefiore, Tel Aviv-Yafo, Israel"
    if "sarona" in latin_key or "\u05e9\u05e8\u05d5\u05e0\u05d4" in folded:
        return "Sarona Market, Tel Aviv-Yafo, Israel"
    return normalized


def is_tel_aviv_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold()
    for punctuation in ("-", "\u2013", "\u2014", "\u05be"):
        normalized = normalized.replace(punctuation, " ")
    normalized = " ".join(normalized.split())
    return normalized in {
        "tel aviv",
        "tel aviv yafo",
        "\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1",
        "\u05ea\u05dc \u05d0\u05d1\u05d9\u05d1 \u05d9\u05e4\u05d5",
    }


def normalize_listing_text(value: str) -> str:
    return (
        value.replace("\u05f4", '"')
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u05f3", "'")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def route_dict(route: WalkingRoute | None) -> dict[str, int] | None:
    return {"minutes": route.minutes, "meters": route.meters} if route else None


def validate_extraction(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "location_query": optional_text(value.get("location_query")),
        "location_text": optional_text(value.get("location_text")),
        "location_confidence": enum_text(
            value.get("location_confidence"),
            "location_confidence",
            {"high", "medium", "low", "unknown"},
        ),
        "listing_type": enum_text(
            value.get("listing_type"),
            "listing_type",
            {"shared", "solo", "unknown"},
        ),
        "price_ils": bounded_integer(value.get("price_ils"), "price_ils", 0, 100000),
        "move_in_signal": enum_text(
            value.get("move_in_signal"),
            "move_in_signal",
            {"match", "mismatch", "flexible", "unknown"},
        ),
        "condition_signal": enum_text(
            value.get("condition_signal"),
            "condition_signal",
            {"excellent", "good", "acceptable", "poor", "unknown"},
        ),
        "shelter_signal": enum_text(
            value.get("shelter_signal"),
            "shelter_signal",
            {"mamad", "shelter", "none", "unknown"},
        ),
        "facts": string_list(value.get("facts"), "facts"),
        "concerns": string_list(value.get("concerns"), "concerns"),
        "unknowns": string_list(value.get("unknowns"), "unknowns"),
    }


def validate_verdict(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": enum_text(
            value.get("category"),
            "category",
            {"recommended", "just_okay", "not_really"},
        ),
        "score": bounded_integer(value.get("score"), "score", 0, 100),
        "summary": required_text(value.get("summary"), "summary"),
        "location_signal": required_text(
            value.get("location_signal"), "location_signal"
        ),
        "shelter_signal": enum_text(
            value.get("shelter_signal"),
            "shelter_signal",
            {"mamad", "shelter", "none", "unknown"},
        ),
        "positives": string_list(value.get("positives"), "positives"),
        "concerns": string_list(value.get("concerns"), "concerns"),
        "unknowns": string_list(value.get("unknowns"), "unknowns"),
    }


def required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalysisError(f"{name} must be a non-empty string")
    return value.strip()


def optional_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def enum_text(value: Any, name: str, options: set[str]) -> str:
    if not isinstance(value, str) or value not in options:
        raise AnalysisError(f"{name} must be one of {sorted(options)}")
    return value


def bounded_integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise AnalysisError(f"{name} must be between {minimum} and {maximum}")
    return value


def string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 12:
        raise AnalysisError(f"{name} must be a list with at most 12 items")
    return [required_text(item, f"{name} item") for item in value]


def unique_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
