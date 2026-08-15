"""Seen-post storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .models import ApartmentPost, ScoreResult


class SeenStore:
    """SQLite-backed dedupe store."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_posts (
                key TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                url TEXT,
                score INTEGER,
                decision TEXT,
                seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def has_seen(self, post: ApartmentPost) -> bool:
        cursor = self.connection.execute(
            "SELECT 1 FROM seen_posts WHERE key = ? LIMIT 1", (post.key,)
        )
        return cursor.fetchone() is not None

    def mark_seen(
        self, post: ApartmentPost, score: Optional[ScoreResult] = None
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO seen_posts (key, source, url, score, decision)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                post.key,
                post.source,
                post.url,
                score.score if score else None,
                score.decision.value if score else None,
            ),
        )
        self.connection.commit()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
