"""Warm-up phases — pure state machine (Bravestep-aligned)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class Phase(str, Enum):
    SETUP = "setup"
    VALUE = "value"
    MENTIONS = "mentions"
    SCALED = "scaled"


class ShadowbanStatus(str, Enum):
    CLEAN = "clean"
    SHADOWBANNED = "shadowbanned"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class WarmupSignals:
    """Measured signals only. Folklore karma totals are NOT hard gates."""

    verified_email: bool
    joined_target_subs: frozenset[str]
    target_subs: frozenset[str]
    per_sub_karma: Mapping[str, int]
    removals_7d: int
    shadowban: ShadowbanStatus
    account_age_days: int
    max_age_gate_days: int
    mention_days: int
    spam_filter_14d: int
    rate_limit_errors: int
    # Advisory display only — never advances phase alone
    total_karma: int = 0


@dataclass(frozen=True)
class TransitionResult:
    next: Phase
    blocked_by: tuple[str, ...] = ()
    advanced: bool = False


ORDER = (Phase.SETUP, Phase.VALUE, Phase.MENTIONS, Phase.SCALED)


def karma_shortfall(signals: WarmupSignals, target: str, gate: int) -> int:
    """Advisory UI helper — not a phase gate."""
    have = int(signals.per_sub_karma.get(target, 0))
    return max(0, gate - have)


def evaluate_transition(phase: Phase, signals: WarmupSignals) -> TransitionResult:
    """
    Advance only on verified-mechanism signals.
    Gate = where you can post; phase = what you may say — keep separate.
    """
    blocked: list[str] = []

    if phase is Phase.SETUP:
        if not signals.verified_email:
            blocked.append("verified_email")
        missing = signals.target_subs - signals.joined_target_subs
        if missing:
            blocked.append(f"join_subs:{','.join(sorted(missing))}")
        if blocked:
            return TransitionResult(phase, tuple(blocked), False)
        return TransitionResult(Phase.VALUE, (), True)

    if phase is Phase.VALUE:
        if signals.shadowban is not ShadowbanStatus.CLEAN:
            blocked.append(f"shadowban:{signals.shadowban.value}")
        if signals.removals_7d > 0:
            blocked.append(f"removals_7d:{signals.removals_7d}")
        if signals.account_age_days < signals.max_age_gate_days:
            blocked.append(
                f"account_age:{signals.account_age_days}<{signals.max_age_gate_days}"
            )
        for sub in sorted(signals.target_subs):
            if int(signals.per_sub_karma.get(sub, 0)) <= 0:
                blocked.append(f"per_sub_karma:{sub}")
        if blocked:
            return TransitionResult(phase, tuple(blocked), False)
        return TransitionResult(Phase.MENTIONS, (), True)

    if phase is Phase.MENTIONS:
        if signals.mention_days < 14:
            blocked.append(f"mention_days:{signals.mention_days}<14")
        if signals.spam_filter_14d > 0:
            blocked.append(f"spam_filter_14d:{signals.spam_filter_14d}")
        if signals.rate_limit_errors > 0:
            blocked.append(f"rate_limit_errors:{signals.rate_limit_errors}")
        if blocked:
            return TransitionResult(phase, tuple(blocked), False)
        return TransitionResult(Phase.SCALED, (), True)

    # SCALED — stay; continuous health enforced by guardrails + worker
    if signals.shadowban is ShadowbanStatus.SHADOWBANNED:
        return TransitionResult(phase, ("shadowban:shadowbanned",), False)
    return TransitionResult(phase, (), False)


def plain_english_blockers(result: TransitionResult) -> list[str]:
    """Founder-facing blockers."""
    labels = {
        "verified_email": "Verify your Reddit email first.",
        "shadowban:shadowbanned": "Account looks shadowbanned — stop posting and check health.",
        "shadowban:unknown": "Shadowban status unknown — re-run health check.",
    }
    out: list[str] = []
    for b in result.blocked_by:
        if b in labels:
            out.append(labels[b])
        elif b.startswith("join_subs:"):
            out.append(f"Join these subs first: {b.split(':', 1)[1]}")
        elif b.startswith("per_sub_karma:"):
            out.append(f"Need positive karma in r/{b.split(':', 1)[1]} (helpful comments).")
        elif b.startswith("removals_7d:"):
            out.append("Recent removals — pause promo and post value-only.")
        elif b.startswith("account_age:"):
            out.append("Account too new for some target sub age gates.")
        elif b.startswith("mention_days:"):
            out.append("Need ~2 weeks of clean disclosed mentions before scaling.")
        elif b.startswith("spam_filter_14d:"):
            out.append("Spam-filter hits in last 14 days — cool down.")
        elif b.startswith("rate_limit_errors:"):
            out.append("Hit rate limits — slow down.")
        else:
            out.append(b)
    return out
