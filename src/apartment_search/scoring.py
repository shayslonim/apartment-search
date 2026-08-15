"""Rule-based apartment scoring with signals tailored to the search brief."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from .models import ApartmentPost, Criteria, Decision, ScoreResult


MONTEFIORE_TERMS = ("montefiore", "מונטיפיורי")
SARONA_TERMS = ("sarona", "שרונה")
WORK_TERMS = ("hahaskala", "ha-haskala", "haskala", "ההשכלה", "השכלה 3")
NEARBY_TERMS = (
    "menachem begin",
    "מנחם בגין",
    "hashmonaim",
    "החשמונאים",
    "hamasger",
    "המסגר",
    "yigal alon",
    "יגאל אלון",
    "nachalat yitzhak",
    "נחלת יצחק",
)
QUALITY_POSITIVE_TERMS = (
    "renovated",
    "maintained",
    "bright",
    "clean",
    "pleasant",
    "balcony",
    "elevator",
    "furnished",
    "משופצת",
    "שמורה",
    "מוארת",
    "נקייה",
    "נקי",
    "נעימה",
    "מרפסת",
    "מעלית",
    "מרוהטת",
)
QUALITY_NEGATIVE_TERMS = (
    "neglected",
    "run down",
    "mold",
    "damp",
    "broken",
    "needs renovation",
    "מוזנחת",
    "עובש",
    "טחב",
    "רטיבות",
    "שבורה",
    "דורשת שיפוץ",
)
CITY_LIFE_TERMS = (
    "cafe",
    "cafes",
    "restaurant",
    "restaurants",
    "bar",
    "bars",
    "nightlife",
    "בתי קפה",
    "בית קפה",
    "מסעדות",
    "ברים",
    "חיי לילה",
)
SHARED_TERMS = ("roommate", "roommates", "shared", "שותף", "שותפה", "שותפים")
SOLO_TERMS = ("studio", "דירה לבד", "סטודיו", "יחידת דיור")
PRICE_CONTEXT_TERMS = (
    "₪",
    "שח",
    'ש"ח',
    "nis",
    "ils",
    "rent",
    "price",
    "מחיר",
    "שכירות",
    "שכר דירה",
)


def score_post(post: ApartmentPost, criteria: Criteria) -> ScoreResult:
    """Score a post using local heuristics."""

    normalized = _normalize(post.text.strip())
    positives: List[str] = []
    negatives: List[str] = []
    unknowns: List[str] = []

    score = 0
    location_score, location_signal = _location_score(normalized)
    score += location_score
    if location_signal != "unknown":
        positives.append(location_signal)
    else:
        unknowns.append("Location is not specific enough")

    commute_score, commute_signal = _commute_score(normalized)
    score += commute_score
    if commute_signal:
        positives.append(commute_signal)
    else:
        unknowns.append(f"Distance to {criteria.work_address} is unknown")

    quality_score, quality_positive, quality_negative = _quality_score(normalized)
    score += quality_score
    positives.extend(quality_positive)
    negatives.extend(quality_negative)
    if not quality_positive and not quality_negative:
        unknowns.append("Apartment condition is unclear")

    listing_type = _listing_type(normalized)
    price = parse_price_ils(post.text)
    price_score, price_positive, price_negative, price_unknown = _price_score(
        price, listing_type, criteria
    )
    score += price_score
    positives.extend(price_positive)
    negatives.extend(price_negative)
    unknowns.extend(price_unknown)

    shelter_score, shelter_signal, shelter_pos, shelter_neg, shelter_unknown = (
        _shelter_score(normalized)
    )
    score += shelter_score
    positives.extend(shelter_pos)
    negatives.extend(shelter_neg)
    unknowns.extend(shelter_unknown)

    move_in_score, move_in_signal = _move_in_score(normalized)
    score += move_in_score
    if move_in_signal:
        positives.append(move_in_signal)
    else:
        unknowns.append("Move-in date is not clearly September or October 2026")

    city_life_score = 5 if _contains_any(normalized, CITY_LIFE_TERMS) else 0
    score += city_life_score
    if city_life_score:
        positives.append("Nearby cafes, restaurants, bars, or city life")

    score = max(0, min(100, score))
    decision = _decision(score, criteria.minimum_score)
    summary = _summary(score, decision, location_signal, price, shelter_signal)

    return ScoreResult(
        score=score,
        decision=decision,
        summary=summary,
        positives=_unique(positives),
        negatives=_unique(negatives),
        unknowns=_unique(unknowns),
        price_ils=price,
        listing_type=listing_type,
        location_signal=location_signal,
        shelter_signal=shelter_signal,
    )


def parse_price_ils(text: str) -> Optional[int]:
    """Extract a likely monthly rent in ILS from a listing."""

    candidates: List[Tuple[int, int]] = []

    for match in re.finditer(r"(?<!\w)(\d{1,2}(?:[.,]\d{1,2})?)\s*[kK]\b", text):
        value = int(float(match.group(1).replace(",", ".")) * 1000)
        if 1500 <= value <= 12000:
            candidates.append((2, value))

    amount_pattern = r"(?<!\d)(\d{1,2}[,.]\d{3}|\d{4,5})(?!\d)"
    for match in re.finditer(amount_pattern, text):
        value = int(match.group(1).replace(",", "").replace(".", ""))
        if not 1500 <= value <= 12000:
            continue
        if 1900 <= value <= 2099:
            continue
        window = _normalize(text[max(0, match.start() - 24) : match.end() + 24])
        context_score = 2 if _contains_any(window, PRICE_CONTEXT_TERMS) else 1
        candidates.append((context_score, value))

    if not candidates:
        return None
    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
    return candidates[0][1]


def _location_score(text: str) -> Tuple[int, str]:
    if _contains_any(text, MONTEFIORE_TERMS):
        return 35, "Montefiore"
    if _contains_any(text, SARONA_TERMS):
        return 30, "Sarona"
    if _contains_any(text, WORK_TERMS):
        return 28, "HaHaskala 3 / work area"
    if _contains_any(text, NEARBY_TERMS):
        return 22, "Nearby central-east Tel Aviv signal"
    tel_aviv = "tel aviv" in text or "תל אביב" in text
    return (8, "unknown") if tel_aviv else (0, "unknown")


def _commute_score(text: str) -> Tuple[int, Optional[str]]:
    walking_terms = ("walk", "walking", "הליכה", "דקות", "minute", "minutes")
    short_terms = ("15", "10", "12", "short", "near", "קרוב", "קצר")
    transit_terms = ("light rail", "bus", "רכבת קלה", "אוטובוס")

    if _contains_any(text, WORK_TERMS):
        return 15, "Direct HaHaskala/work-area mention"
    if _contains_any(text, SARONA_TERMS) and _contains_any(text, walking_terms):
        return 13, "Walking-distance Sarona signal"
    if _contains_any(text, walking_terms) and _contains_any(text, short_terms):
        return 10, "Short walking-distance signal"
    if _contains_any(text, transit_terms) and _contains_any(text, short_terms):
        return 7, "Short public-transit signal"
    return 0, None


def _quality_score(text: str) -> Tuple[int, List[str], List[str]]:
    positives = []
    negatives = []
    score = 8

    if _contains_any(text, QUALITY_POSITIVE_TERMS):
        positives.append("Maintained, renovated, bright, or pleasant condition")
        score += 10
    if _contains_any(text, QUALITY_NEGATIVE_TERMS):
        negatives.append(
            "Condition warning: neglected, damp, mold, or needs renovation"
        )
        score -= 18

    return max(-15, min(20, score)), positives, negatives


def _price_score(
    price: Optional[int], listing_type: str, criteria: Criteria
) -> Tuple[int, List[str], List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []
    unknowns: List[str] = []

    if price is None:
        unknowns.append("Price is missing")
        return 3, positives, negatives, unknowns

    if listing_type == "shared":
        if price <= criteria.max_shared_price_ils:
            positives.append("Shared-room price is within target budget")
            return 15, positives, negatives, unknowns
        if price <= criteria.stretch_shared_price_ils:
            positives.append("Shared-room price is slightly over target")
            return 10, positives, negatives, unknowns
        negatives.append("Shared-room price is over stretch budget")
        return 2, positives, negatives, unknowns

    if listing_type == "solo":
        if price <= criteria.max_solo_price_ils:
            positives.append("Solo-apartment price is within target budget")
            return 15, positives, negatives, unknowns
        negatives.append("Solo-apartment price is over target budget")
        return 2, positives, negatives, unknowns

    if price <= criteria.max_shared_price_ils:
        positives.append("Price is within shared-apartment target")
        return 12, positives, negatives, unknowns
    if price <= criteria.max_solo_price_ils:
        positives.append("Price is within stretch/solo range")
        return 8, positives, negatives, unknowns
    negatives.append("Price appears high for the target search")
    return 2, positives, negatives, unknowns


def _shelter_score(
    text: str,
) -> Tuple[int, str, List[str], List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []
    unknowns: List[str] = []

    no_mamad = bool(
        re.search(r"(אין|ללא)\s*(ממד|ממ\"ד)|no\s+mamad", text)
    )
    no_shelter = bool(
        re.search(r"(אין|ללא)\s*(מקלט|מרחב מוגן)|no\s+shelter", text)
    )
    has_mamad = bool(re.search(r"\b(mamad|safe room)\b|ממד|ממ\"ד", text))
    has_shelter = bool(re.search(r"\b(shelter)\b|מקלט|מרחב מוגן", text))
    has_mamad = has_mamad and not no_mamad
    has_shelter = has_shelter and not no_shelter

    if has_mamad:
        positives.append("Mamad inside the apartment")
        return 10, "mamad", positives, negatives, unknowns
    if has_shelter:
        positives.append("Shelter in building or nearby protected space")
        return 6, "shelter", positives, negatives, unknowns
    if no_mamad and no_shelter:
        negatives.append("Explicitly says there is no Mamad and no shelter")
        return -8, "none", positives, negatives, unknowns
    if no_mamad:
        negatives.append("No Mamad stated")
        unknowns.append("Shelter availability is unclear")
        return -2, "no_mamad_unknown_shelter", positives, negatives, unknowns

    unknowns.append("Mamad/shelter information is missing")
    return 2, "unknown", positives, negatives, unknowns


def _move_in_score(text: str) -> Tuple[int, Optional[str]]:
    september = (
        "september 2026",
        "sep 2026",
        "sept 2026",
        "09/2026",
        "9/2026",
        "ספטמבר 2026",
        "ספטמבר",
    )
    october = ("october 2026", "oct 2026", "10/2026", "אוקטובר 2026", "אוקטובר")
    if _contains_any(text, september):
        return 5, "Move-in matches September 2026"
    if _contains_any(text, october):
        return 5, "Move-in matches October 2026"
    return 0, None


def _listing_type(text: str) -> str:
    if _contains_any(text, SHARED_TERMS):
        return "shared"
    if _contains_any(text, SOLO_TERMS):
        return "solo"
    return "unknown"


def _decision(score: int, minimum_score: int) -> Decision:
    if score >= minimum_score:
        return Decision.SEND
    if score >= max(0, minimum_score - 15):
        return Decision.REVIEW
    return Decision.REJECT


def _summary(
    score: int,
    decision: Decision,
    location_signal: str,
    price: Optional[int],
    shelter_signal: str,
) -> str:
    price_label = f"{price} ILS" if price else "price unknown"
    return (
        f"{decision.value.upper()} score {score}: {location_signal}, "
        f"{price_label}, shelter={shelter_signal}"
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold())


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term.casefold() in text for term in terms)


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
