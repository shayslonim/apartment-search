# Apartment Search Site

Hosted receiver and dashboard for Apartment Search.

## Runtime flow

1. Groups Watcher sends a Facebook post to
   `POST /webhooks/groups-watcher?token=...`.
2. The receiver validates the webhook secret, normalizes the payload, scores
   the listing, and stores it in D1.
3. Duplicate posts are ignored.
4. Strong matches are optionally sent to Telegram.
5. The protected dashboard displays ranked listings. A listing title opens the
   original Facebook post when Groups Watcher supplies `post_url`.

## Environment

Copy `.env.example` to `.dev.vars` for local development and replace both
secrets. Telegram values are optional.

## Commands

```bash
npm install
npm run dev
npm test
npm run lint
```

The health endpoint is `GET /health`.
