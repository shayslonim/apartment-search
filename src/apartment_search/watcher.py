"""Run apartment scans and notifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .analyzer import analyze_post
from .config import AppConfig, resolve_relative
from .models import ApartmentPost, Decision, ScoreResult
from .sources import SourceError, fetch_posts
from .storage import SeenStore
from .telegram import TelegramError, TelegramNotifier


@dataclass
class ProcessedPost:
    """Result of processing a single post."""

    post: ApartmentPost
    score: ScoreResult
    delivered: bool = False
    error: str = ""


@dataclass
class RunSummary:
    """Summary of one watcher run."""

    fetched: int = 0
    skipped_seen: int = 0
    processed: List[ProcessedPost] = field(default_factory=list)
    source_errors: List[str] = field(default_factory=list)

    @property
    def sent(self) -> int:
        return sum(1 for item in self.processed if item.delivered)

    @property
    def send_candidates(self) -> int:
        return sum(1 for item in self.processed if item.score.decision == Decision.SEND)


def run_once(
    config: AppConfig,
    dry_run: bool = False,
    limit: int = 0,
    login: bool = False,
) -> RunSummary:
    """Run one scan over all configured sources."""

    summary = RunSummary()
    store_path = resolve_relative(config.base_dir, config.storage.path)
    notifier = TelegramNotifier.from_config(config.telegram)

    with SeenStore(Path(store_path)) as store:
        for source in config.sources:
            try:
                posts = fetch_posts(source, config, login=login)
            except SourceError as exc:
                summary.source_errors.append(str(exc))
                continue

            if limit > 0:
                posts = posts[:limit]
            summary.fetched += len(posts)

            for post in posts:
                if store.has_seen(post):
                    summary.skipped_seen += 1
                    continue

                score = analyze_post(post, config.criteria, config.scoring)
                processed = ProcessedPost(post=post, score=score)

                if score.decision == Decision.SEND and notifier and not dry_run:
                    try:
                        notifier.send(post, score)
                        processed.delivered = True
                    except TelegramError as exc:
                        processed.error = str(exc)

                summary.processed.append(processed)

                should_mark_seen = not dry_run and (
                    score.decision != Decision.SEND
                    or notifier is None
                    or processed.delivered
                )
                if should_mark_seen:
                    store.mark_seen(post, score)

    return summary
