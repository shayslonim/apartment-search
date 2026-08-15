"""Post source adapters."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .config import AppConfig, SourceConfig, resolve_relative
from .models import ApartmentPost


class SourceError(RuntimeError):
    """Raised when a source cannot be read."""


def fetch_posts(
    source: SourceConfig,
    config: AppConfig,
    login: bool = False,
) -> List[ApartmentPost]:
    """Fetch posts from one configured source."""

    if source.type == "json":
        if source.path is None:
            raise SourceError(f"{source.name}: json source is missing path")
        posts_path = resolve_relative(config.base_dir, source.path)
        return list(_fetch_json_posts(source, posts_path))
    if source.type == "facebook_browser":
        if source.url is None:
            raise SourceError(f"{source.name}: facebook source is missing url")
        return FacebookBrowserSource(config).fetch(source, login=login)
    raise SourceError(f"Unsupported source type: {source.type}")


def _fetch_json_posts(source: SourceConfig, path: Path) -> Iterable[ApartmentPost]:
    if not path.exists():
        raise SourceError(f"{source.name}: JSON posts file does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceError(f"{source.name}: invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, list):
        raise SourceError(f"{source.name}: JSON posts file must contain a list")

    for index, raw in enumerate(data):
        if isinstance(raw, str):
            yield ApartmentPost(source=source.name, text=raw)
            continue
        if not isinstance(raw, dict):
            raise SourceError(
                f"{source.name}: post {index} must be an object or string"
            )
        text = raw.get("text")
        if not text or not isinstance(text, str):
            raise SourceError(f"{source.name}: post {index} is missing text")
        yield ApartmentPost(
            source=source.name,
            text=text,
            url=_optional_str(raw.get("url")),
            posted_at=_optional_str(raw.get("posted_at")),
            author=_optional_str(raw.get("author")),
            raw=raw,
        )


class FacebookBrowserSource:
    """Scrape visible Facebook posts through a user's browser session."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch(self, source: SourceConfig, login: bool = False) -> List[ApartmentPost]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SourceError(
                "Playwright is required for facebook_browser sources. "
                "Install with: python -m pip install -e '.[facebook]'"
            ) from exc

        profile_dir = resolve_relative(
            self.config.base_dir, self.config.facebook.browser_profile_dir
        )
        profile_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self.config.facebook.headless,
            )
            page = context.new_page()
            page.goto(source.url, wait_until="domcontentloaded", timeout=60_000)
            wait_for_login = login or self.config.facebook.wait_for_login
            if wait_for_login and not self.config.facebook.headless:
                print(
                    "If Facebook asks for login, complete it in the opened browser, "
                    "then press Enter here."
                )
                input()
            page.wait_for_timeout(self.config.facebook.wait_seconds * 1000)
            for _ in range(max(0, self.config.facebook.scrolls)):
                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(1200)
            raw_posts = page.evaluate(_FACEBOOK_POST_EXTRACTOR)
            context.close()

        posts: List[ApartmentPost] = []
        for raw in raw_posts:
            text = str(raw.get("text", "")).strip()
            if len(text) < 40:
                continue
            posts.append(
                ApartmentPost(
                    source=source.name,
                    text=text,
                    url=_best_facebook_url(raw.get("urls", [])),
                    author=_optional_str(raw.get("author")),
                    raw=raw,
                )
            )
        return posts


_FACEBOOK_POST_EXTRACTOR = """
() => Array.from(document.querySelectorAll('div[role="article"]'))
  .slice(0, 80)
  .map((article) => {
    const anchors = Array.from(article.querySelectorAll('a[href]'));
    const urls = anchors.map((anchor) => anchor.href).filter(Boolean);
    const author = anchors.map((anchor) => anchor.innerText || '')
      .find((text) => text.trim().length > 1);
    return {
      text: article.innerText || '',
      urls,
      author
    };
  })
"""


def _best_facebook_url(urls: Iterable[Any]) -> Optional[str]:
    candidates = [str(url) for url in urls if isinstance(url, str)]
    preferred = (
        "/posts/",
        "/permalink/",
        "story_fbid=",
        "multi_permalinks=",
        "fbid=",
    )
    for marker in preferred:
        for url in candidates:
            if marker in url:
                return _canonical_facebook_url(url)
    return _canonical_facebook_url(candidates[0]) if candidates else None


def _canonical_facebook_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    keep = {}
    for key in ("story_fbid", "fbid", "id", "multi_permalinks"):
        if key in query:
            keep[key] = query[key][0]
    path = re.sub(r"/+$", "", parsed.path)
    return urlunparse(
        (parsed.scheme, parsed.netloc, path, "", urlencode(keep), "")
    )


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
