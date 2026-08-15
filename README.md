# Apartment Search

Apartment Search receives Facebook group posts from Groups Watcher, scores them
against your Montefiore/Sarona/HaHaskala 3 criteria, deduplicates already-seen
posts, and optionally sends strong matches to Telegram. The recommended
receiver is the hosted Sites app in `site/`; the Python receiver remains
available as a local fallback.

Groups Watcher runs in your logged-in Chrome session and sends matching posts to
Apartment Search through a stable hosted webhook. The receiver stays online,
but the Groups Watcher extension still requires Chrome and the computer to be
running. The optional Playwright source remains available as a fallback.
Neither approach bypasses Facebook access controls.

## Hosted Sites receiver

The hosted component provides:

- a secret-protected Groups Watcher webhook;
- durable D1 storage and duplicate detection;
- the same free rule-based scoring criteria as the Python app;
- an access-key-protected dashboard;
- direct Facebook links on listing titles;
- optional Telegram delivery for strong matches.

See `site/README.md` for local development. Runtime secrets are managed by
Sites and are never committed.

## Local Python fallback

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

For the optional Playwright fallback:

```bash
python -m pip install ".[dev,facebook]"
python -m playwright install chromium
```

## Configure

Copy the starter config:

```bash
cp config.example.json config.json
```

Create a webhook secret and keep the terminal session open:

```bash
export GROUPS_WATCHER_WEBHOOK_SECRET="replace-with-a-long-random-value"
```

Start Apartment Search in dry-run mode for the first test:

```bash
apartment-search serve-webhook --config config.json --dry-run
```

In Groups Watcher, choose **Custom Webhook** and enter:

```text
http://127.0.0.1:8787/webhooks/groups-watcher?token=YOUR_SECRET
```

Replace `YOUR_SECRET` with the same value exported above. The receiver accepts
the documented single-post and batched payload formats. If the extension refuses
a localhost URL, use an HTTPS tunnel and keep the token in the webhook URL.

Use broad Groups Watcher keywords so Apartment Search performs the detailed
filtering. Keep auto-commenting disabled.

`json` sources remain available for pasted/exported posts while testing:

```json
[
  {
    "text": "Montefiore room with roommates, renovated, 3800 ILS, September 2026, Mamad in apartment",
    "url": "https://example.com/post/1"
  }
]
```

The optional `facebook_browser` source can still read a Facebook group directly:

```json
{
  "name": "facebook-group-example",
  "type": "facebook_browser",
  "url": "https://www.facebook.com/groups/YOUR_GROUP"
}
```

Telegram is optional. To enable it, set `"telegram.enabled": true` and export:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

OpenAI scoring is optional. The local rule scorer works without an API key. To
enable AI scoring, set `"scoring.use_openai": true` and export:

```bash
export OPENAI_API_KEY="..."
```

## Run

Score one pasted post:

```bash
apartment-search score "Montefiore room, renovated, 3800 ILS, September 2026, Mamad" --json
```

Run a dry scan without sending Telegram messages or marking posts seen:

```bash
apartment-search scan --config config.json --dry-run
```

First Playwright fallback run, with time to complete login:

```bash
apartment-search scan --config config.json --login --dry-run
```

When Telegram is configured and you want to mark posts as seen:

```bash
apartment-search serve-webhook --config config.json
```

## Test

```bash
pytest
```

## Notes

- Deduplication is stored in `.apartment-search/seen.sqlite3`.
- The webhook health check is available at `http://127.0.0.1:8787/health`.
- Groups Watcher and this receiver must both be running to collect posts.
- Facebook markup changes often, so the browser scraper is intentionally small
  and heuristic-based.
- Keep tokens and `.apartment-search/` out of git.
