#!/usr/bin/env python3
"""CLI for my maturity timeline tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cmd_checklist(_: argparse.Namespace) -> None:
    print(
        """
Account maturity kickoff checklist (Sun)
========================================
[ ] Working on feat/reddit-channel concepts (pure modules here mirror that branch)
[ ] Prod path = OAuth + evaluate_transition — NOT :4200 demo shortcuts
[ ] SOCIAVAULT_KEY set for listening/gate samples (Erik may use scrape; product prefers Vault)
[ ] REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET (web app) for founder OAuth
[ ] CHANNEL_TOKEN_ENCRYPTION_KEYS=v1:<base64-32B> for token at rest
[ ] Never: auto-post, auto-vote, buy aged accounts, ship gate-fail playbooks to founders
[ ] Erik listening API :8000 · Maturity API :8100
[ ] Blockers for Chris: list missing secrets above

Done when: this checklist filled + blockers written for Chris.
""".strip()
    )


def cmd_gates(args: argparse.Namespace) -> None:
    from maturity.adapters.erik_corpus import infer_gates_from_erik
    from maturity.domain.farmability import is_blocked

    subs = [s.strip() for s in args.subs.split(",") if s.strip()]
    estimates = infer_gates_from_erik(subs)
    for e in estimates:
        print(
            json.dumps(
                {
                    "subreddit": e.subreddit,
                    "karma_gate": e.karma_gate,
                    "source": e.source.value,
                    "sample_size": e.sample_size,
                    "avoid": is_blocked(e.subreddit),
                    "notes": e.notes,
                },
                indent=2,
            )
        )


def cmd_guardrail(args: argparse.Namespace) -> None:
    from maturity.domain.guardrails import Draft, RateState, check_action

    result = check_action(
        Draft(text=args.text, canonical_link=args.link, is_promo=args.promo),
        [],
        RateState(shadowbanned=args.shadowbanned),
    )
    print(json.dumps({"block": result.block, "violations": [v.value for v in result.violations]}, indent=2))


def cmd_tfa(args: argparse.Namespace) -> None:
    from maturity.domain.tfa_audit import CampaignContext, audit_campaign

    result = audit_campaign(
        CampaignContext(
            account_age_days=args.age,
            days_since_last_activity_before_burst=args.dormant,
            product_mention=args.promo,
            hired_upvotes=args.upvotes,
            friend_support_comments=args.friends,
            bought_aged_account=args.bought,
            formulaic_username=False,
            plagiarized_comments=False,
            abnormal_engagement=False,
            multi_account_herd=False,
        )
    )
    print(
        json.dumps(
            {
                "ok": result.ok,
                "findings": [f.__dict__ for f in result.findings],
            },
            indent=2,
        )
    )


def cmd_api(_: argparse.Namespace) -> None:
    import uvicorn
    from maturity.config import API_HOST, API_PORT

    print(f"Maturity API http://{API_HOST}:{API_PORT}/docs")
    uvicorn.run("maturity.api.server:app", host=API_HOST, port=API_PORT, reload=False)


def cmd_test(_: argparse.Namespace) -> None:
    import unittest

    loader = unittest.TestLoader()
    suite = loader.discover(str(Path(__file__).parent / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def main() -> None:
    p = argparse.ArgumentParser(description="Bravestep account maturity (me)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("checklist", help="Sun kickoff checklist").set_defaults(func=cmd_checklist)

    g = sub.add_parser("gates", help="Wed: infer gates from Erik corpus")
    g.add_argument("--subs", required=True, help="comma-separated subreddit names")
    g.set_defaults(func=cmd_gates)

    gr = sub.add_parser("guardrail", help="Thu: check a draft")
    gr.add_argument("--text", required=True)
    gr.add_argument("--link", default=None)
    gr.add_argument("--promo", action="store_true")
    gr.add_argument("--shadowbanned", action="store_true")
    gr.set_defaults(func=cmd_guardrail)

    t = sub.add_parser("tfa", help="Thu: TFA campaign audit")
    t.add_argument("--age", type=int, default=30)
    t.add_argument("--dormant", type=int, default=None)
    t.add_argument("--promo", action="store_true")
    t.add_argument("--upvotes", action="store_true")
    t.add_argument("--friends", action="store_true")
    t.add_argument("--bought", action="store_true")
    t.set_defaults(func=cmd_tfa)

    sub.add_parser("api", help="Run maturity API on :8100").set_defaults(func=cmd_api)
    sub.add_parser("test", help="Run unit tests").set_defaults(func=cmd_test)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
