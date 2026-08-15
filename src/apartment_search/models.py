"""Core data models for the apartment watcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Dict, List, Optional


class Decision(str, Enum):
    """Notification decision for a scored apartment post."""

    SEND = "send"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True)
class ApartmentPost:
    """A normalized apartment post collected from any source."""

    source: str
    text: str
    url: Optional[str] = None
    posted_at: Optional[str] = None
    author: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Return a stable dedupe key for the post."""

        identity = self.url or self.text
        digest = sha256(identity.strip().encode("utf-8")).hexdigest()
        return f"{self.source}:{digest}"


@dataclass(frozen=True)
class Criteria:
    """Apartment search preferences."""

    work_address: str = "HaHaskala 3, Tel Aviv"
    preferred_areas: List[str] = field(
        default_factory=lambda: ["Montefiore", "Sarona", "HaHaskala 3"]
    )
    max_shared_price_ils: int = 4000
    stretch_shared_price_ils: int = 4500
    max_solo_price_ils: int = 4500
    move_in_months: List[str] = field(
        default_factory=lambda: ["September 2026", "October 2026"]
    )
    minimum_score: int = 70


@dataclass(frozen=True)
class ScoreResult:
    """Structured scoring output for a post."""

    score: int
    decision: Decision
    summary: str
    positives: List[str] = field(default_factory=list)
    negatives: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    price_ils: Optional[int] = None
    listing_type: str = "unknown"
    location_signal: str = "unknown"
    shelter_signal: str = "unknown"
    source: str = "rules"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the score for JSON output."""

        return {
            "score": self.score,
            "decision": self.decision.value,
            "summary": self.summary,
            "positives": self.positives,
            "negatives": self.negatives,
            "unknowns": self.unknowns,
            "price_ils": self.price_ils,
            "listing_type": self.listing_type,
            "location_signal": self.location_signal,
            "shelter_signal": self.shelter_signal,
            "source": self.source,
        }
