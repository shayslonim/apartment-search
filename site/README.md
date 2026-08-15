# Apartment Search Site

Hosted receiver, analysis queue, and protected dashboard for Apartment Search.

## Runtime flow

1. Groups Watcher sends a Facebook post to
   `POST /webhooks/groups-watcher?token=...`.
2. The receiver validates the webhook secret, normalizes the payload,
   deduplicates the post, and stores a pending job in D1.
3. The local worker claims a job through `POST /api/analysis/claim` using the
   analyzer secret.
4. The worker returns a structured result through
   `POST /api/analysis/results`.
5. The site validates and stores the result as Recommended, Just Okay, or Not
   Really. Recommended results are optionally sent to Telegram.
6. The dashboard displays every completed listing, verified walking times, and
   a direct Facebook link when `post_url` is available.

Failed jobs are retried up to five times. A processing claim becomes available
again after 30 minutes if a worker stops before returning a result.

## Environment

Copy `.env.example` to `.dev.vars` for local development and replace:

- `GROUPS_WATCHER_WEBHOOK_SECRET`
- `DASHBOARD_SECRET`
- `LOCAL_ANALYZER_SECRET`

Telegram values are optional.

## Commands

```bash
npm install
npm run dev
npm test
npm run lint
npm run db:generate
```

The health endpoint is `GET /health`.
