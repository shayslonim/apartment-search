"""Receive and normalize Groups Watcher webhook deliveries."""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

from .config import AppConfig, ConfigError
from .models import ApartmentPost
from .watcher import RunSummary, process_posts

MAX_REQUEST_BYTES = 2 * 1024 * 1024


class GroupsWatcherError(ConfigError):
    """Raised when the Groups Watcher receiver cannot start."""


class GroupsWatcherPayloadError(ValueError):
    """Raised when a webhook payload has an unsupported shape."""


class GroupsWatcherServer(ThreadingHTTPServer):
    """Threaded webhook server that shuts request workers down cleanly."""

    daemon_threads = True
    allow_reuse_address = True


def posts_from_payload(payload: Any) -> List[ApartmentPost]:
    """Normalize a documented Groups Watcher payload into apartment posts."""

    if not isinstance(payload, dict):
        raise GroupsWatcherPayloadError("Payload must be a JSON object")

    if "data" in payload:
        raw_posts = [payload["data"]]
    elif "posts" in payload:
        raw_posts = payload["posts"]
        if not isinstance(raw_posts, list):
            raise GroupsWatcherPayloadError("Payload posts must be a list")
    else:
        raise GroupsWatcherPayloadError(
            "Payload must contain a data object or posts list"
        )

    if not raw_posts:
        raise GroupsWatcherPayloadError("Payload does not contain any posts")

    posts = []
    for index, raw in enumerate(raw_posts):
        if not isinstance(raw, dict):
            raise GroupsWatcherPayloadError(f"Post {index} must be an object")
        posts.append(_post_from_payload(raw, index))
    return posts


def create_server(
    config: AppConfig,
    *,
    dry_run: bool = False,
    host: Optional[str] = None,
    port: Optional[int] = None,
    secret: Optional[str] = None,
) -> GroupsWatcherServer:
    """Create a configured webhook server without starting its event loop."""

    webhook = config.groups_watcher
    if not webhook.enabled:
        raise GroupsWatcherError("groups_watcher.enabled must be true")

    resolved_secret = secret or os.environ.get(webhook.secret_env)
    if not resolved_secret:
        raise GroupsWatcherError(f"{webhook.secret_env} must be set")

    bind_host = host if host is not None else webhook.host
    bind_port = port if port is not None else webhook.port
    expected_path = webhook.path.rstrip("/") or "/"

    class WebhookHandler(BaseHTTPRequestHandler):
        server_version = "ApartmentSearchWebhook/1.0"

        def do_GET(self) -> None:
            path = urlsplit(self.path).path.rstrip("/") or "/"
            if path == "/health":
                self._send_json(200, {"status": "ok"})
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            request_url = urlsplit(self.path)
            request_path = request_url.path.rstrip("/") or "/"
            if request_path != expected_path:
                self._send_json(404, {"error": "not_found"})
                return
            if not self._is_authorized(request_url.query, resolved_secret):
                self._send_json(401, {"error": "unauthorized"})
                return

            try:
                payload = self._read_payload()
                posts = posts_from_payload(payload)
                summary = process_posts(config, posts, dry_run=dry_run)
            except GroupsWatcherPayloadError as exc:
                self._send_json(400, {"error": "invalid_payload", "detail": str(exc)})
                return
            except Exception as exc:  # noqa: BLE001 - HTTP boundary returns JSON.
                print(
                    json.dumps(
                        {"event": "webhook_error", "error": str(exc)},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                self._send_json(500, {"error": "processing_failed"})
                return

            response = _summary_payload(summary)
            print(json.dumps(response, ensure_ascii=False), flush=True)
            self._send_json(200, response)

        def log_message(self, format: str, *args: object) -> None:
            # BaseHTTPRequestHandler logs the query string, which contains the token.
            return

        def _is_authorized(self, query: str, expected: str) -> bool:
            query_token = parse_qs(query).get("token", [""])[0]
            header_token = self.headers.get("X-Webhook-Secret", "")
            authorization = self.headers.get("Authorization", "")
            bearer_token = ""
            if authorization.startswith("Bearer "):
                bearer_token = authorization[7:]
            provided = header_token or bearer_token or query_token
            return bool(provided) and hmac.compare_digest(provided, expected)

        def _read_payload(self) -> Any:
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "0")
            except ValueError as exc:
                raise GroupsWatcherPayloadError("Invalid Content-Length") from exc
            if length <= 0:
                raise GroupsWatcherPayloadError("Request body is empty")
            if length > MAX_REQUEST_BYTES:
                raise GroupsWatcherPayloadError("Request body is too large")
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GroupsWatcherPayloadError(
                    "Request body is not valid JSON"
                ) from exc

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return GroupsWatcherServer((bind_host, bind_port), WebhookHandler)


def serve(
    config: AppConfig,
    *,
    dry_run: bool = False,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> None:
    """Run the Groups Watcher webhook receiver until interrupted."""

    server = create_server(config, dry_run=dry_run, host=host, port=port)
    bind_host, bind_port = server.server_address[:2]
    path = config.groups_watcher.path
    print(f"Listening on http://{bind_host}:{bind_port}{path}")
    print(
        "Add ?token=<secret> to the webhook URL, using the value from "
        f"{config.groups_watcher.secret_env}."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping webhook receiver.")
    finally:
        server.server_close()


def _post_from_payload(raw: Dict[str, Any], index: int) -> ApartmentPost:
    body = _optional_string(raw.get("body"))
    if not body:
        raise GroupsWatcherPayloadError(f"Post {index} is missing body")

    group_name = _optional_string(raw.get("group_name"))
    group_id = _optional_string(raw.get("group_id"))
    source_name = group_name or group_id or "unknown-group"
    return ApartmentPost(
        source=f"groups-watcher:{source_name}",
        text=body,
        url=_optional_string(raw.get("post_url")),
        posted_at=_optional_string(raw.get("timestamp")),
        author=_optional_string(raw.get("poster_name")),
        raw=raw,
    )


def _summary_payload(summary: RunSummary) -> Dict[str, Any]:
    return {
        "event": "groups_watcher_delivery",
        "accepted": summary.fetched,
        "processed": len(summary.processed),
        "skipped_seen": summary.skipped_seen,
        "send_candidates": summary.send_candidates,
        "sent": summary.sent,
        "delivery_errors": [item.error for item in summary.processed if item.error],
    }


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    value = value.strip()
    return value or None
