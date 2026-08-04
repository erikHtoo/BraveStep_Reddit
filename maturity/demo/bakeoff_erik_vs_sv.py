#!/usr/bin/env python3
"""Erik scrape vs SociaVault bake-off — price / speed / errors.

Usage:
  cd /Users/m2/Desktop/05-JobProjects/BraveStep
  export PYTHONPATH=.
  # optional:
  export SOCIAVAULT_KEY=...
  maturity/.venv/bin/python -m maturity.demo.bakeoff_erik_vs_sv --subs startups,saas --limit 10
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Repo root = erik-reddit when maturity is nested; else BraveStep workspace
_HERE = Path(__file__).resolve().parent
_MATURITY = _HERE.parent
_CANDIDATE = _MATURITY.parent
if (_CANDIDATE / "main.py").exists() and (_CANDIDATE / "export").is_dir():
    ROOT = _CANDIDATE
    ERIK = ROOT
else:
    ROOT = _CANDIDATE
    ERIK = ROOT / "erik-reddit"
OUT_JSON = _HERE / "bakeoff_results.json"
OUT_MD = _HERE / "bakeoff_results.md"


@dataclass
class RunResult:
    provider: str
    ok: bool
    seconds: float
    items: int = 0
    http_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    approx_cost_usd: float | None = None


def run_erik_scrape(subs: list[str], limit: int) -> RunResult:
    py = ERIK / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)
    t0 = time.perf_counter()
    items = 0
    errors: list[str] = []
    notes: list[str] = []
    for sub in subs:
        cmd = [str(py), "main.py", sub, "--limit", str(limit), "--no-media", "--no-comments"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ERIK),
                capture_output=True,
                text=True,
                timeout=180,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode != 0:
                errors.append(f"r/{sub} exit={proc.returncode}")
            if "HTTP 403" in out or "403" in out and "HTTP" in out:
                errors.append(f"r/{sub} saw 403")
            if "HTTP 502" in out:
                notes.append(f"r/{sub} mirror 502 (may still succeed via old.reddit)")
            if "SQLite:" in out:
                notes.append(f"r/{sub} wrote SQLite")
            # crude count from "Saved N new posts" / "SCRAPE COMPLETE"
            for line in out.splitlines():
                if "Saved" in line and "posts" in line:
                    try:
                        n = int("".join(ch for ch in line.split("Saved")[1] if ch.isdigit()) or "0")
                        items += n
                    except ValueError:
                        pass
            if items == 0 and "SCRAPE COMPLETE" in out:
                notes.append(f"r/{sub} completed — parse count from DB after")
        except subprocess.TimeoutExpired:
            errors.append(f"r/{sub} timeout")
        except Exception as e:
            errors.append(f"r/{sub} {e}")
    seconds = time.perf_counter() - t0

    # Prefer DB truth for item count
    try:
        import sqlite3

        db = ERIK / "data" / "reddit_scraper.db"
        conn = sqlite3.connect(db)
        live = 0
        for sub in subs:
            live += conn.execute(
                "SELECT COUNT(*) FROM posts WHERE lower(subreddit)=lower(?) AND source != 'demo_seed'",
                (sub,),
            ).fetchone()[0]
        conn.close()
        if live:
            items = live
            notes.append(f"db_live_posts={live}")
    except Exception as e:
        notes.append(f"db_count_failed={e}")

    return RunResult(
        provider="erik_scrape",
        ok=items > 0 and not any("403" in e for e in errors),
        seconds=round(seconds, 2),
        items=items,
        http_errors=errors,
        notes=notes + ["cost≈$0 infra (your IP/proxy); ban risk not priced"],
        approx_cost_usd=0.0,
    )


def run_erik_gates(subs: list[str]) -> RunResult:
    t0 = time.perf_counter()
    try:
        from maturity.adapters.erik_corpus import infer_gates_from_erik

        estimates = infer_gates_from_erik(subs)
        seconds = time.perf_counter() - t0
        return RunResult(
            provider="erik_gates_from_sqlite",
            ok=len(estimates) > 0,
            seconds=round(seconds, 3),
            items=sum(e.sample_size for e in estimates),
            notes=[f"{e.subreddit}:P5≈{e.karma_gate} n={e.sample_size}" for e in estimates],
            approx_cost_usd=0.0,
        )
    except Exception as e:
        return RunResult(
            provider="erik_gates_from_sqlite",
            ok=False,
            seconds=round(time.perf_counter() - t0, 3),
            http_errors=[str(e)],
        )


def run_sociavault(subs: list[str], limit: int) -> RunResult:
    key = os.getenv("SOCIAVAULT_KEY", "").strip()
    if not key:
        return RunResult(
            provider="sociavault",
            ok=False,
            seconds=0.0,
            notes=["SOCIAVAULT_KEY not set — skipped. Put key in maturity/.env then re-run."],
        )

    # Ensure adapter sees key even if config was imported earlier
    os.environ["SOCIAVAULT_KEY"] = key
    import importlib
    import maturity.config as cfg
    import maturity.adapters.sociavault as sv

    importlib.reload(cfg)
    importlib.reload(sv)

    t0 = time.perf_counter()
    items = 0
    errors: list[str] = []
    notes: list[str] = []
    credits_hint = 0
    try:
        for sub in subs:
            try:
                t_sub = time.perf_counter()
                authors = sv.subreddit_new_authors(sub, limit=limit)
                items += len(authors)
                credits_hint += 1  # docs: 1 credit / subreddit request
                notes.append(
                    f"r/{sub} authors={len(authors)} in {time.perf_counter()-t_sub:.2f}s (~1 credit)"
                )
            except sv.SociaVaultError as e:
                errors.append(f"r/{sub} {e}")
            try:
                t_s = time.perf_counter()
                posts = sv.search_posts(sub, limit=limit)
                notes.append(
                    f"r/{sub} search_posts={len(posts)} in {time.perf_counter()-t_s:.2f}s (~1 credit)"
                )
                items += len(posts)
                credits_hint += 1
            except sv.SociaVaultError as e:
                errors.append(f"r/{sub} search {e}")
    except Exception as e:
        errors.append(str(e))

    seconds = time.perf_counter() - t0
    notes.append(f"approx_credits_used≈{credits_hint} (1 credit/req per docs)")
    notes.append("Fill $ from SociaVault plan after dashboard credit price check")
    return RunResult(
        provider="sociavault",
        ok=items > 0 and not errors,
        seconds=round(seconds, 2),
        items=items,
        http_errors=errors,
        notes=notes,
        approx_cost_usd=None,
    )


def write_reports(results: list[RunResult], subs: list[str], limit: int) -> None:
    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "subs": subs,
        "limit_per_sub": limit,
        "results": [asdict(r) for r in results],
        "verdict_hint": (
            "Prefer SociaVault for Bravestep product reads if speed+reliability win; "
            "keep Erik scrape as research corpus if cost≈0 and 403 rate acceptable."
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    lines = [
        "# Erik vs SociaVault bake-off",
        "",
        f"Ran: `{payload['ran_at']}`",
        f"Subs: {', '.join(subs)} · limit/sub: {limit}",
        "",
        "| Provider | OK | Seconds | Items | Cost USD | Errors |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        err = "; ".join(r.http_errors) if r.http_errors else "—"
        cost = "—" if r.approx_cost_usd is None else str(r.approx_cost_usd)
        lines.append(
            f"| {r.provider} | {r.ok} | {r.seconds} | {r.items} | {cost} | {err} |"
        )
    lines += ["", "## Notes"]
    for r in results:
        lines.append(f"### {r.provider}")
        for n in r.notes:
            lines.append(f"- {n}")
        lines.append("")
    lines += [
        "## Decision frame for Chris",
        "- **100% Erik** only if 403 rate low + SQLite pipeline stable + legal/ToS OK",
        "- **100% SociaVault** if product needs reliable datacenter reads",
        "- **Combine** (recommended default): SV for product listening; Erik for cheap research corpus",
        "",
    ]
    OUT_MD.write_text("\n".join(lines))
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")


def main() -> None:
    # Load maturity/.env if present
    env_path = ROOT / "maturity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    p = argparse.ArgumentParser()
    p.add_argument("--subs", default="startups,saas")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--skip-scrape", action="store_true", help="Only gates + SociaVault")
    args = p.parse_args()
    subs = [s.strip().lstrip("r/") for s in args.subs.split(",") if s.strip()]

    results: list[RunResult] = []
    if not args.skip_scrape:
        print("=== Erik live scrape ===")
        results.append(run_erik_scrape(subs, args.limit))
    print("=== Erik gates from SQLite ===")
    results.append(run_erik_gates(subs))
    print("=== SociaVault ===")
    results.append(run_sociavault(subs, args.limit))

    write_reports(results, subs, args.limit)
    print(json.dumps([asdict(r) for r in results], indent=2))


if __name__ == "__main__":
    main()
