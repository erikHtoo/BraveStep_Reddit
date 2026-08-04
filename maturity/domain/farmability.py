"""Farmability scoring + karma-farm blocklist."""

from __future__ import annotations

from dataclasses import dataclass


# Living list — never send founders here (vote-manip / farm traps)
KARMA_FARM_BLOCKLIST = frozenset(
    {
        "freekarma4u",
        "freekarma4you",
        "karmafarm",
        "karmafarming",
        "getkarma",
        "upvotetrading",
        "upvoteexchange",
        "karmacourt",
        "freegold",
    }
)


@dataclass(frozen=True)
class FarmabilityScore:
    subreddit: str
    score: float  # 0..1 higher = easier for newcomers
    avoid: bool
    reasons: tuple[str, ...]


def normalize_sub(name: str) -> str:
    return name.strip().lstrip("r/").lower()


def is_blocked(subreddit: str) -> bool:
    return normalize_sub(subreddit) in KARMA_FARM_BLOCKLIST


def karma_farmability(
    subreddit: str,
    *,
    avg_comment_score: float,
    newbie_author_share: float,
    gate_ease: float,
) -> FarmabilityScore:
    """
    Simple weighted score for research / routing.
    gate_ease: 1.0 = no/low gate, 0.0 = hard gate.
    newbie_author_share: 0..1 fraction of recent authors with low karma.
    """
    sub = normalize_sub(subreddit)
    if sub in KARMA_FARM_BLOCKLIST:
        return FarmabilityScore(sub, 0.0, True, ("blocklist:karma_farm",))

    # Clamp inputs
    avg = max(0.0, min(avg_comment_score, 50.0)) / 50.0
    newbie = max(0.0, min(newbie_author_share, 1.0))
    ease = max(0.0, min(gate_ease, 1.0))
    score = 0.45 * avg + 0.25 * newbie + 0.30 * ease
    reasons = (
        f"avg_comment={avg_comment_score:.1f}",
        f"newbie_share={newbie_author_share:.2f}",
        f"gate_ease={gate_ease:.2f}",
    )
    return FarmabilityScore(sub, round(score, 3), False, reasons)
