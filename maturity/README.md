# Account Maturity (me) — Half B

Pairs with Erik’s listening scraper in `../erik-reddit`.

| Half | Owner | Repo folder | Job |
|---|---|---|---|
| A Listening | Erik | `erik-reddit/` | Scrape → classify → DB → realtime |
| B Maturity | me | `maturity/` | OAuth → health → phases → gates → guardrails → HITL |

Later these pure domain modules port into Bravestep `feat/reddit-channel` (TypeScript). Do not re-derive — mirror contracts.

## Hard rules

- Observe + coach only. **Never** auto-post / auto-vote.
- Phase advances on **measured signals** only (email, per-sub karma, removals, shadowban…). Folklore “need 500 karma” is display-only.
- Product listening prefers **SociaVault**. Erik HTML/mirror scrape = research corpus input for gates — not the long-term product path.
- Never buy aged accounts. Never ship gate-failed / TFA-fail playbooks to real founders.
- `:4200` demo shortcuts ≠ prod. Prod = encrypted OAuth + `evaluate_transition` + observe worker.

## Week map (Excel)

| Day | My deliverable | Command |
|---|---|---|
| Sun | Kickoff checklist | `python -m maturity.cli checklist` |
| Mon | OAuth + health | set Reddit app secrets · `python -m maturity.cli api` · `/v1/oauth/*` |
| Tue | Observe worker | `/v1/observe` after tokens stored |
| Wed | Gates + farmability | `python -m maturity.cli gates --subs saas,startups` (needs Erik DB) |
| Thu | Guardrails + TFA | `python -m maturity.cli guardrail …` / `tfa …` |
| Fri | E2E path | connect → observe → guardrail → human submit (manual) |
| Sat | Demo + notes | `demo/DEMO.md` |

## Setup

```bash
cd /Users/m2/Desktop/05-JobProjects/BraveStep
python3 -m venv maturity/.venv
source maturity/.venv/bin/activate
pip install -r maturity/requirements.txt
cp maturity/.env.example maturity/.env   # fill secrets locally
export PYTHONPATH=.
python -m maturity.cli test
python -m maturity.cli api               # http://127.0.0.1:8100/docs
```

Erik API (if running): `http://127.0.0.1:8000`  
Maturity API: `http://127.0.0.1:8100`

## Layout

```text
maturity/
  domain/       pure logic — phases, gates, farmability, guardrails, tfa
  adapters/     SociaVault, Erik SQLite, Reddit OAuth, encrypted token store
  worker/       observe-only health loop
  api/          FastAPI surface
  cli.py
  tests/
  demo/
```

## Join contract with Erik

- Read-only: `ERIK_REDDIT_DB` → `posts` / `comments` for P5 gate samples + farmability research.
- Gate notes always declare when post-score is used as a **weak karma proxy**.
- Live / prod gate samples should move to SociaVault or Reddit OAuth `/new` — not HTML mirrors.
