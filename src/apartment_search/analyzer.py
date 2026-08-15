"""Scoring orchestration."""

from __future__ import annotations

from .config import ScoringConfig
from .models import ApartmentPost, Criteria, ScoreResult
from .openai_scorer import OpenAIScoringError, score_with_openai
from .scoring import score_post


def analyze_post(
    post: ApartmentPost,
    criteria: Criteria,
    scoring_config: ScoringConfig,
) -> ScoreResult:
    """Score a post, using OpenAI when enabled and falling back to rules."""

    rule_score = score_post(post, criteria)
    if not scoring_config.use_openai:
        return rule_score

    try:
        return score_with_openai(post, criteria, scoring_config.openai_model)
    except OpenAIScoringError as exc:
        unknowns = list(rule_score.unknowns)
        unknowns.append(f"OpenAI scoring unavailable: {exc}")
        return ScoreResult(
            score=rule_score.score,
            decision=rule_score.decision,
            summary=rule_score.summary,
            positives=rule_score.positives,
            negatives=rule_score.negatives,
            unknowns=unknowns,
            price_ils=rule_score.price_ils,
            listing_type=rule_score.listing_type,
            location_signal=rule_score.location_signal,
            shelter_signal=rule_score.shelter_signal,
            source="rules_fallback",
        )
