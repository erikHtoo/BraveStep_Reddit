# Friday / Saturday demo script (Chris · 5–7 min)

## Before you start

```bash
# From erik-reddit repo root (or workspace with both halves)
python main.py --api                                      # :8000
PYTHONPATH=. python -m maturity.cli api                   # :8100
python maturity/demo/serve_visual.py                      # :8200
```

Open **http://127.0.0.1:8200/** → **Run full demo**.

## Path

1. **Split** — Erik listening `:8000` · my maturity `:8100` · visual `:8200`.
2. **Health** — `no_auto_post` / `no_auto_vote` / `hitl_only`.
3. **Transition** — email false → blocked; email true → `setup` → `value`.
4. **Guardrails** — shortener + promo without disclosure → `block: true`.
5. **TFA** — bought aged account → `ok: false` (do not ship to real founders).
6. **Gates** — Erik SQLite and/or SociaVault; tiny samples = `estimate`.
7. **Bake-off** — SV works; live scrape can 403 → product listening prefers SV.
8. **Honest** — Bravestep prod needs Chris secrets + Tri migrations; not claiming prod-done.

## Hand Chris

- `maturity/CONTRACT.md` — names to mirror into `feat/reddit-channel`
- `maturity/demo/GTM_COACH_COPY.md` — founder-facing lines
- `maturity/demo/bakeoff_results.md` — Erik vs SV numbers

## Do not demo

- Auto-submit / auto-vote  
- Buying accounts  
- “Erik scrape = 100% Bravestep listening”
