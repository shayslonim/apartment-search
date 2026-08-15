# Apartment Search

Apartment Search is a local MVP for watching Tel Aviv apartment posts, scoring
them against your Montefiore/Sarona/HaHaskala 3 criteria, deduplicating
already-seen posts, and optionally sending strong matches to Telegram.

It does not bypass Facebook login or access controls. For Facebook sources it
opens a normal local Chromium profile through Playwright; you log in yourself,
and the watcher only reads posts visible to that browser session.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For Facebook browser scraping:

```bash
python -m pip install -e ".[dev,facebook]"
python -m playwright install chromium
```

## Configure

Copy the starter config and edit the source URLs:

```bash
cp config.example.json config.json
```

Use `json` sources for pasted/exported posts while testing:

```json
[
  {
    "text": "Montefiore room with roommates, renovated, 3800 ILS, September 2026, Mamad in apartment",
    "url": "https://example.com/post/1"
  }
]
```

Use `facebook_browser` sources for Facebook group/search pages:

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

First Facebook run, with time to complete login:

```bash
apartment-search scan --config config.json --login --dry-run
```

When Telegram is configured and you want to mark posts as seen:

```bash
apartment-search scan --config config.json
```

## Test

```bash
pytest
```

## Notes

- Deduplication is stored in `.apartment-search/seen.sqlite3`.
- Facebook markup changes often, so the browser scraper is intentionally small
  and heuristic-based.
- Keep tokens and `.apartment-search/` out of git.
