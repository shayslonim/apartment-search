# Apartment Search

Apartment Search receives Facebook apartment posts from Groups Watcher, queues
them in a hosted site, analyzes them with a local Ollama model, calculates real
walking routes, deduplicates posts, and shows every completed result in one of
three categories:

- **Recommended**: strong, actionable matches.
- **Just Okay**: plausible listings with compromises or missing information.
- **Not Really**: listings that materially miss the search.

## Production flow

1. The Groups Watcher browser extension sends a post to the stable hosted
   webhook.
2. The site authenticates, normalizes, deduplicates, and stores the post as a
   pending analysis job.
3. A local worker on the Mac claims the job over an authenticated outbound
   connection. Ollama remains private on `localhost`.
4. `qwen3:8b` extracts listing type, price, date, location, condition, and
   protection facts in a constrained JSON format.
5. The worker geocodes the listing with OpenStreetMap and obtains pedestrian
   route time and distance to HaHaskala 3 and Sarona Market.
6. The model applies the personal search guidelines to the post, extracted
   facts, and verified routes.
7. The hosted site validates and stores the final structured result. Recommended
   listings can optionally be sent to Telegram.

The hosted receiver remains online when the Mac is off. The local analysis queue
resumes when the Mac is back on. Groups Watcher itself still requires Brave or
Chrome and the Mac to be running to detect new Facebook posts.

## Local analyzer

Requirements:

- Ollama running on `http://127.0.0.1:11434`.
- The `qwen3:8b` model.
- `LOCAL_ANALYZER_SECRET` matching the hosted Sites secret.

Install the Python package:

```bash
python3 -m venv .venv
.venv/bin/pip install ".[dev]"
```

Run one queued job:

```bash
LOCAL_ANALYZER_SECRET="..." .venv/bin/apartment-search analyze-jobs --once
```

Run continuously:

```bash
LOCAL_ANALYZER_SECRET="..." .venv/bin/apartment-search analyze-jobs
```

Geocoding and route responses are cached in
`.apartment-search/map-cache.sqlite3`. The worker identifies itself to public
OpenStreetMap services, limits request frequency, and does not disable TLS
verification.

## Hosted site

The Sites app in `site/` provides the webhook, D1 queue, worker APIs, protected
dashboard, direct Facebook links, and optional Telegram delivery. Runtime
secrets are managed by Sites and are never committed.

See `site/README.md` for hosted development and environment details.

## Test

```bash
.venv/bin/pytest
.venv/bin/ruff check src/apartment_search/local_analyzer.py \
  src/apartment_search/analysis_worker.py tests/test_local_analyzer.py
cd site && npm test && npm run lint
```

## Legacy fallbacks

The earlier local JSON, Playwright, local webhook, and deterministic scoring
commands remain available for isolated testing. They are not part of the
production Groups Watcher analysis flow.
