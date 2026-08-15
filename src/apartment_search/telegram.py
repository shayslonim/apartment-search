"""Telegram delivery."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .config import TelegramConfig
from .models import ApartmentPost, ScoreResult


class TelegramError(RuntimeError):
    """Raised when Telegram delivery fails."""


@dataclass(frozen=True)
class TelegramNotifier:
    """Send apartment matches to Telegram."""

    bot_token: str
    chat_id: str

    @classmethod
    def from_config(cls, config: TelegramConfig) -> Optional["TelegramNotifier"]:
        if not config.enabled:
            return None
        token = os.environ.get(config.bot_token_env)
        chat_id = os.environ.get(config.chat_id_env)
        if not token or not chat_id:
            raise TelegramError(
                f"{config.bot_token_env} and {config.chat_id_env} must be set"
            )
        return cls(bot_token=token, chat_id=chat_id)

    def send(self, post: ApartmentPost, score: ScoreResult) -> None:
        message = format_telegram_message(post, score)
        endpoint = (
            "https://api.telegram.org/bot"
            f"{urllib.parse.quote(self.bot_token)}/sendMessage"
        )
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": False,
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TelegramError(f"Telegram HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise TelegramError(f"Telegram request failed: {exc}") from exc

        if not body.get("ok"):
            raise TelegramError(f"Telegram rejected message: {body}")


def format_telegram_message(post: ApartmentPost, score: ScoreResult) -> str:
    """Format one scored match as a compact Telegram card."""

    lines = [
        f"Apartment match: {score.score}/100 ({score.decision.value})",
        score.summary,
    ]
    group_name = post.raw.get("group_name")
    if group_name:
        lines.append(f"Group: {group_name}")
    if post.author:
        lines.append(f"Posted by: {post.author}")
    if score.price_ils:
        lines.append(f"Price: {score.price_ils} ILS")
    lines.append(f"Location: {score.location_signal}")
    lines.append(f"Protection: {score.shelter_signal}")
    if score.positives:
        lines.append("Good: " + "; ".join(score.positives[:4]))
    if score.negatives:
        lines.append("Watch: " + "; ".join(score.negatives[:3]))
    if score.unknowns:
        lines.append("?: " + "; ".join(score.unknowns[:3]))
    if post.url:
        lines.append(post.url)
    return "\n".join(lines)
