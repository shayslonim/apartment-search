"""Command line interface for Apartment Search."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from .analysis_worker import build_worker
from .config import ConfigError, load_config, resolve_config_path, write_default_config
from .groups_watcher import serve as serve_groups_watcher
from .models import ApartmentPost, Criteria
from .scoring import score_post
from .watcher import run_once


def main(argv: list[str] | None = None) -> None:
    """Run the Apartment Search CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except ConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apartment-search",
        description="Watch and score Tel Aviv apartment posts.",
    )
    subparsers = parser.add_subparsers(required=True)

    init_parser = subparsers.add_parser("init-config", help="write a starter config")
    init_parser.add_argument("--path", default="config.json", help="config path")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing config",
    )
    init_parser.set_defaults(handler=_handle_init_config)

    scan_parser = subparsers.add_parser("scan", help="run one scan")
    scan_parser.add_argument("--config", default="config.json", help="config path")
    scan_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print matches without sending Telegram messages or marking seen",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="maximum posts per source; 0 means no limit",
    )
    scan_parser.add_argument(
        "--login",
        action="store_true",
        help="pause after opening Facebook so you can complete login",
    )
    scan_parser.set_defaults(handler=_handle_scan)

    webhook_parser = subparsers.add_parser(
        "serve-webhook",
        help="receive Groups Watcher webhook deliveries",
    )
    webhook_parser.add_argument("--config", default="config.json", help="config path")
    webhook_parser.add_argument("--host", help="override webhook bind host")
    webhook_parser.add_argument(
        "--port",
        type=int,
        help="override webhook bind port",
    )
    webhook_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="process posts without sending Telegram messages or marking them seen",
    )
    webhook_parser.set_defaults(handler=_handle_serve_webhook)

    score_parser = subparsers.add_parser("score", help="score one pasted post")
    score_parser.add_argument("text", help="post text")
    score_parser.add_argument(
        "--json",
        action="store_true",
        help="print the structured score JSON",
    )
    score_parser.set_defaults(handler=_handle_score)

    analyze_parser = subparsers.add_parser(
        "analyze-jobs",
        help="process hosted posts with the local Ollama analyzer",
    )
    analyze_parser.add_argument(
        "--site-url",
        default=os.getenv(
            "APARTMENT_SEARCH_SITE_URL",
            "https://apartment-search.shaysks.chatgpt.site",
        ),
        help="hosted Apartment Search URL",
    )
    analyze_parser.add_argument(
        "--secret-env",
        default="LOCAL_ANALYZER_SECRET",
        help="environment variable containing the analyzer secret",
    )
    analyze_parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        help="local Ollama model",
    )
    analyze_parser.add_argument(
        "--ollama-url",
        default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        help="local Ollama API URL",
    )
    analyze_parser.add_argument(
        "--cache-path",
        default=".apartment-search/map-cache.sqlite3",
        help="persistent geocoding and route cache",
    )
    analyze_parser.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        help="seconds to wait when the hosted queue is empty",
    )
    analyze_parser.add_argument(
        "--once",
        action="store_true",
        help="claim at most one post and exit",
    )
    analyze_parser.set_defaults(handler=_handle_analyze_jobs)

    return parser


def _handle_init_config(args: argparse.Namespace) -> None:
    path = Path(args.path).expanduser().resolve()
    write_default_config(path, force=args.force)
    print(f"Wrote {path}")


def _handle_scan(args: argparse.Namespace) -> None:
    config = load_config(resolve_config_path(args.config))
    summary = run_once(
        config,
        dry_run=args.dry_run,
        limit=args.limit,
        login=args.login,
    )

    for item in summary.processed:
        payload = {
            "post": {
                "source": item.post.source,
                "url": item.post.url,
                "text_preview": item.post.text[:180],
            },
            "score": item.score.to_dict(),
            "delivered": item.delivered,
            "error": item.error,
        }
        print(json.dumps(payload, ensure_ascii=False))

    print(
        "Summary: "
        f"fetched={summary.fetched} "
        f"processed={len(summary.processed)} "
        f"skipped_seen={summary.skipped_seen} "
        f"send_candidates={summary.send_candidates} "
        f"sent={summary.sent}"
    )
    for error in summary.source_errors:
        print(f"Source error: {error}", file=sys.stderr)


def _handle_serve_webhook(args: argparse.Namespace) -> None:
    config = load_config(resolve_config_path(args.config))
    serve_groups_watcher(
        config,
        dry_run=args.dry_run,
        host=args.host,
        port=args.port,
    )


def _handle_score(args: argparse.Namespace) -> None:
    post = ApartmentPost(source="manual", text=args.text)
    result = score_post(post, Criteria())
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.summary)


def _handle_analyze_jobs(args: argparse.Namespace) -> None:
    secret = os.getenv(args.secret_env)
    if not secret:
        raise SystemExit(f"Missing analyzer secret in {args.secret_env}")
    if args.poll_seconds < 1:
        raise SystemExit("--poll-seconds must be at least 1")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    worker, cache = build_worker(
        site_url=args.site_url,
        secret=secret,
        model_name=args.model,
        ollama_url=args.ollama_url,
        cache_path=Path(args.cache_path).expanduser().resolve(),
    )
    try:
        if args.once:
            worker.run_once()
        else:
            worker.run_forever(poll_seconds=args.poll_seconds)
    finally:
        cache.close()


if __name__ == "__main__":
    main()
