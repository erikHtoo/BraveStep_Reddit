"""Observe-only warm-up worker — never posts or votes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from maturity.adapters.reddit_oauth import fetch_me, fetch_me_karma
from maturity.adapters.token_store import load_connection
from maturity.domain.phases import (
    Phase,
    ShadowbanStatus,
    TransitionResult,
    WarmupSignals,
    evaluate_transition,
    plain_english_blockers,
)


@dataclass
class AccountState:
    case_id: str
    username: str
    phase: Phase
    target_subs: frozenset[str]
    joined_subs: frozenset[str]
    last_result: TransitionResult | None = None
    last_checked_at: str | None = None


@dataclass(frozen=True)
class ObserveReport:
    case_id: str
    username: str
    phase: Phase
    next_phase: Phase
    advanced: bool
    blockers: list[str]
    verified_email: bool
    per_sub_karma: dict[str, int]
    checked_at: str


def build_signals(
    *,
    verified_email: bool,
    target_subs: frozenset[str],
    joined_subs: frozenset[str],
    per_sub_karma: dict[str, int],
    account_age_days: int,
    total_karma: int,
    removals_7d: int = 0,
    shadowban: ShadowbanStatus = ShadowbanStatus.UNKNOWN,
    max_age_gate_days: int = 0,
    mention_days: int = 0,
    spam_filter_14d: int = 0,
    rate_limit_errors: int = 0,
) -> WarmupSignals:
    return WarmupSignals(
        verified_email=verified_email,
        joined_target_subs=joined_subs,
        target_subs=target_subs,
        per_sub_karma=per_sub_karma,
        removals_7d=removals_7d,
        shadowban=shadowban,
        account_age_days=account_age_days,
        max_age_gate_days=max_age_gate_days,
        mention_days=mention_days,
        spam_filter_14d=spam_filter_14d,
        rate_limit_errors=rate_limit_errors,
        total_karma=total_karma,
    )


def observe_once(state: AccountState) -> ObserveReport:
    """
    Pull health via OAuth and evaluate phase transition.
    Does NOT submit content. Does NOT vote.
    """
    conn = load_connection(state.case_id)
    me = fetch_me(conn.access_token)
    karma_map = fetch_me_karma(conn.access_token)

    per_sub: dict[str, int] = {}
    for sub in state.target_subs:
        row = karma_map.get(sub) or karma_map.get(sub.lower()) or {}
        # comment-first warm-up
        per_sub[sub] = int(row.get("comment_karma") or 0) + int(row.get("link_karma") or 0)

    age_days = int(max(0, (time.time() - me.created_utc) / 86400))
    signals = build_signals(
        verified_email=me.verified_email,
        target_subs=state.target_subs,
        joined_subs=state.joined_subs,
        per_sub_karma=per_sub,
        account_age_days=age_days,
        total_karma=me.total_karma,
        shadowban=ShadowbanStatus.UNKNOWN,  # wire logged-out probe in prod path
    )
    result = evaluate_transition(state.phase, signals)
    if result.advanced:
        state.phase = result.next
    state.last_result = result
    checked = datetime.now(timezone.utc).isoformat()
    state.last_checked_at = checked

    return ObserveReport(
        case_id=state.case_id,
        username=me.name or state.username,
        phase=state.phase if result.advanced else state.phase,
        next_phase=result.next,
        advanced=result.advanced,
        blockers=plain_english_blockers(result),
        verified_email=me.verified_email,
        per_sub_karma=per_sub,
        checked_at=checked,
    )
