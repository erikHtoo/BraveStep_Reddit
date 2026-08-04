# BraveStep Reddit — Listening + Maturity (lab)

Joint lab: **Erik** cleaned scraper (`BraveStep_Ver0.1`) + **my** account maturity half.

| Half | Path | Job |
|---|---|---|
| Listening | `main.py` | Scrape → **CSV + SQLite** |
| Maturity | `maturity/` (`:8100`) | OAuth → phases → gates → guardrails → HITL |

## Hard rules

- Maturity = observe/coach only — **never** auto-post / auto-vote
- Product listening preference: **SociaVault**; Erik scrape = research corpus / backup
- Secrets only in `maturity/.env` (gitignored)

## Quick start

```bash
# Listening scrape (Erik cleaned CLI)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py startups --limit 10 --no-media --no-comments

# Maturity API
python3 -m venv maturity/.venv && source maturity/.venv/bin/activate
pip install -r maturity/requirements.txt
cp maturity/.env.example maturity/.env   # add SOCIAVAULT_KEY etc.
export PYTHONPATH=.
python -m maturity.cli test
python -m maturity.cli api               # http://127.0.0.1:8100/docs

# Visual demo (maturity API up)
python maturity/demo/serve_visual.py     # http://127.0.0.1:8200/
```

## Scrape → maturity join

`main.py` writes CSV under `data/r_<sub>/` and also `data/reddit_scraper.db`.  
If live scrape 403s but CSV exists:

```bash
python import_csv_to_sqlite.py --csv data/r_startups/posts.csv --sub startups
```

## Bake-off

```bash
export PYTHONPATH=.
python -m maturity.demo.bakeoff_erik_vs_sv --subs startups,saas --limit 10
```

See `maturity/CONTRACT.md` + `maturity/demo/DEMO.md`.
