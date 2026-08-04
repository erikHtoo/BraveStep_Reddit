# BraveStep Reddit — Listening + Maturity (lab)

Joint lab: the Reddit listener feeds a local CSV/SQLite corpus and hosted Neon PostgreSQL database; the maturity service is observe/coach only.

| Half | Path | Job |
|---|---|---|
| Listening | `main.py` | Scrape → CSV + SQLite + Neon PostgreSQL |
| Maturity | `maturity/` (`:8100`) | OAuth → phases → gates → guardrails → HITL |

## Hard rules

- Maturity never auto-posts or auto-votes.
- Keep secrets in ignored `.env` files only.

## Reddit listener

The default scrape is post-only: title, author, timestamp, subreddit, permalink, content, score, flair, and related metadata. Every valid post is upserted to Neon by its immutable Reddit ID; reruns refresh live fields rather than creating duplicates.

1. Create a Neon PostgreSQL project (PostgreSQL 17 recommended).
2. Copy `.env.example` to `.env` and set its `DATABASE_URL`.
3. Install and scrape:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python main.py startups --limit 100
   ```

Use `--comments` or `--media` only when the optional local comment CSV or media downloads are wanted.

The scraper also maintains the existing CSV and SQLite listener outputs for maturity workflows. If a live scrape fails but CSV exists:

```bash
python import_csv_to_sqlite.py --csv data/r_startups/posts.csv --sub startups
```

## Scheduled hosting

`.github/workflows/scrape.yml` runs the scraper every six hours using GitHub Actions.

1. Add `DATABASE_URL` as an Actions repository secret; optionally add `PROXY_URL`.
2. Add `REDDIT_TARGET` as a repository variable. Optionally set `REDDIT_IS_USER=true` and `SCRAPE_LIMIT=100`.
3. Enable Actions or select **Run workflow** for an immediate run.

Never commit a Neon connection string. The workflow stores the durable hosted post record in PostgreSQL and does not upload local backup data.

## Maturity service

```bash
python3 -m venv maturity/.venv && source maturity/.venv/bin/activate
pip install -r maturity/requirements.txt
cp maturity/.env.example maturity/.env
export PYTHONPATH=.
python -m maturity.cli test
python -m maturity.cli api
```

See `maturity/CONTRACT.md` and `maturity/demo/DEMO.md`.
