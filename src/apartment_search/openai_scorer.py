"""Optional OpenAI-backed scoring."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .models import ApartmentPost, Criteria, Decision, ScoreResult


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIScoringError(RuntimeError):
    """Raised when OpenAI scoring cannot complete."""


def score_with_openai(
    post: ApartmentPost,
    criteria: Criteria,
    model: str,
    api_key: Optional[str] = None,
    timeout_seconds: int = 30,
) -> ScoreResult:
    """Score a post with the OpenAI Responses API."""

    token = api_key or os.environ.get("OPENAI_API_KEY")
    if not token:
        raise OpenAIScoringError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": _system_prompt(),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "criteria": _criteria_payload(criteria),
                                "post": {
                                    "source": post.source,
                                    "url": post.url,
                                    "posted_at": post.posted_at,
                                    "author": post.author,
                                    "text": post.text,
                                },
                            },
                            ensure_ascii=False,
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "apartment_score",
                "strict": True,
                "schema": _score_schema(),
            }
        },
    }

    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OpenAIScoringError(f"OpenAI HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OpenAIScoringError(f"OpenAI request failed: {exc}") from exc

    parsed = _extract_output_json(body)
    return ScoreResult(
        score=int(parsed["score"]),
        decision=Decision(parsed["decision"]),
        summary=str(parsed["summary"]),
        positives=list(parsed["positives"]),
        negatives=list(parsed["negatives"]),
        unknowns=list(parsed["unknowns"]),
        price_ils=parsed.get("price_ils"),
        listing_type=str(parsed["listing_type"]),
        location_signal=str(parsed["location_signal"]),
        shelter_signal=str(parsed["shelter_signal"]),
        source="openai",
    )


def _criteria_payload(criteria: Criteria) -> Dict[str, Any]:
    return {
        "work_address": criteria.work_address,
        "preferred_areas": criteria.preferred_areas,
        "max_shared_price_ils": criteria.max_shared_price_ils,
        "stretch_shared_price_ils": criteria.stretch_shared_price_ils,
        "max_solo_price_ils": criteria.max_solo_price_ils,
        "move_in_months": criteria.move_in_months,
        "minimum_score": criteria.minimum_score,
    }


def _system_prompt() -> str:
    return (
        "You score Tel Aviv apartment listings for one renter. "
        "Prioritize Montefiore or walking distance to Sarona, then distance to "
        "HaHaskala 3, apartment condition, price, and Mamad/shelter. "
        "Keep listings with missing shelter data but flag the unknown. "
        "Use the supplied JSON schema only."
    )


def _score_schema() -> Dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "score",
            "decision",
            "summary",
            "positives",
            "negatives",
            "unknowns",
            "price_ils",
            "listing_type",
            "location_signal",
            "shelter_signal",
        ],
        "properties": {
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "decision": {"type": "string", "enum": ["send", "review", "reject"]},
            "summary": {"type": "string"},
            "positives": string_array,
            "negatives": string_array,
            "unknowns": string_array,
            "price_ils": {"type": ["integer", "null"]},
            "listing_type": {"type": "string", "enum": ["shared", "solo", "unknown"]},
            "location_signal": {"type": "string"},
            "shelter_signal": {
                "type": "string",
                "enum": [
                    "mamad",
                    "shelter",
                    "none",
                    "no_mamad_unknown_shelter",
                    "unknown",
                ],
            },
        },
    }


def _extract_output_json(body: Dict[str, Any]) -> Dict[str, Any]:
    output = body.get("output")
    if not isinstance(output, list):
        raise OpenAIScoringError("OpenAI response did not include output")

    for item in output:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and "text" in content:
                try:
                    parsed = json.loads(content["text"])
                except json.JSONDecodeError as exc:
                    raise OpenAIScoringError(
                        "OpenAI output was not valid JSON"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise OpenAIScoringError("OpenAI output JSON was not an object")
                return parsed

    raise OpenAIScoringError("OpenAI response did not include output_text JSON")
