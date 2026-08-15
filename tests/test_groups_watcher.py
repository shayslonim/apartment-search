import json
import threading
import urllib.error
import urllib.request

import pytest

from apartment_search.config import (
    AppConfig,
    GroupsWatcherConfig,
    StorageConfig,
)
from apartment_search.groups_watcher import (
    GroupsWatcherPayloadError,
    create_server,
    posts_from_payload,
)
from apartment_search.models import Criteria
from apartment_search.scoring import score_post
from apartment_search.telegram import format_telegram_message


def test_posts_from_single_delivery():
    posts = posts_from_payload(
        {
            "message": "New post in Tel Aviv Apartments",
            "data": {
                "group_name": "Tel Aviv Apartments",
                "poster_name": "Dana",
                "post_url": "https://facebook.com/groups/1/posts/2",
                "body": "Montefiore room, renovated, 3800 ILS, September 2026",
                "timestamp": "2026-08-15T10:00:00Z",
            },
        }
    )

    assert len(posts) == 1
    assert posts[0].source == "groups-watcher:Tel Aviv Apartments"
    assert posts[0].author == "Dana"
    assert posts[0].url == "https://facebook.com/groups/1/posts/2"


def test_posts_from_batch_delivery():
    posts = posts_from_payload(
        {
            "posts": [
                {"group_id": "123", "body": "First apartment"},
                {"group_id": "123", "body": "Second apartment"},
            ]
        }
    )

    assert [post.text for post in posts] == [
        "First apartment",
        "Second apartment",
    ]


def test_posts_from_extension_delivery():
    posts = posts_from_payload(
        {
            "message": "New FB Post Detected",
            "data": {
                "group_id": "982821351800566",
                "profile_name": "Carlos Rosmaninho",
                "post_url": (
                    "https://www.facebook.com/groups/982821351800566/"
                    "posts/8787558701326753/"
                ),
                "post_text": "MOCK REQUEST",
                "time_posted": "12/3/2024, 4:50:59 PM",
            },
        }
    )

    assert posts[0].source == "groups-watcher:982821351800566"
    assert posts[0].text == "MOCK REQUEST"
    assert posts[0].author == "Carlos Rosmaninho"


def test_payload_requires_post_body():
    with pytest.raises(GroupsWatcherPayloadError, match="missing body"):
        posts_from_payload({"data": {"group_name": "Apartments"}})


def test_groups_watcher_metadata_is_in_telegram_message():
    post = posts_from_payload(
        {
            "data": {
                "group_name": "Tel Aviv Apartments",
                "poster_name": "Dana",
                "body": "Montefiore room, renovated, 3800 ILS, Mamad",
            }
        }
    )[0]

    message = format_telegram_message(post, score_post(post, Criteria()))

    assert "Group: Tel Aviv Apartments" in message
    assert "Posted by: Dana" in message


def test_webhook_authenticates_and_deduplicates(tmp_path):
    config = AppConfig(
        sources=[],
        storage=StorageConfig(path="seen.sqlite3"),
        groups_watcher=GroupsWatcherConfig(enabled=True, port=0),
        base_dir=tmp_path,
    )
    server = create_server(config, secret="test-secret")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    payload = {
        "data": {
            "group_name": "Tel Aviv Apartments",
            "post_url": "https://facebook.com/groups/1/posts/99",
            "body": (
                "Montefiore room with roommates, renovated, 3800 ILS, "
                "September 2026, Mamad"
            ),
        }
    }

    try:
        with pytest.raises(urllib.error.HTTPError) as unauthorized:
            _post_json(port, payload, token="wrong-secret")
        assert unauthorized.value.code == 401

        first = _post_json(port, payload, token="test-secret")
        second = _post_json(port, payload, token="test-secret")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert first["accepted"] == 1
    assert first["processed"] == 1
    assert first["send_candidates"] == 1
    assert second["processed"] == 0
    assert second["skipped_seen"] == 1


def _post_json(port, payload, token):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhooks/groups-watcher?token={token}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))
