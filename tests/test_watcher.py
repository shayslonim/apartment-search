import json

from apartment_search.config import load_config
from apartment_search.watcher import run_once


def test_run_once_processes_json_source_without_marking_dry_run(tmp_path):
    posts_path = tmp_path / "posts.json"
    posts_path.write_text(
        json.dumps(
            [
                {
                    "text": (
                        "Montefiore room with roommates, renovated, 3800 ILS, "
                        "September 2026, Mamad"
                    ),
                    "url": "https://example.com/post/1",
                }
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {"name": "posts", "type": "json", "path": "posts.json"}
                ],
                "storage": {"path": "seen.sqlite3"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    first = run_once(config, dry_run=True)
    second = run_once(config, dry_run=True)

    assert len(first.processed) == 1
    assert len(second.processed) == 1


def test_run_once_marks_seen_when_not_dry_run(tmp_path):
    posts_path = tmp_path / "posts.json"
    posts_path.write_text(
        json.dumps([{"text": "Tel Aviv room 3500 ILS", "url": "https://e.test/1"}]),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {"name": "posts", "type": "json", "path": "posts.json"}
                ],
                "storage": {"path": "seen.sqlite3"},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    first = run_once(config)
    second = run_once(config)

    assert len(first.processed) == 1
    assert second.skipped_seen == 1
