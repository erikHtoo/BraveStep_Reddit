"""Subreddit gate inference — P5 survivors (Bravestep-aligned)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class GateSource(str, Enum):
    RULE_TEXT = "rule_text"
    ACTIVE = "active"
    PASSIVE = "passive"
    ESTIMATE = "estimate"


class GateKind(str, Enum):
    TOTAL = "total_karma"
    SUB = "sub_karma"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuthorSample:
    author: str
    karma: int  # best available karma signal for the sample


@dataclass(frozen=True)
class GateEstimate:
    subreddit: str
    karma_gate: int | None
    gate_kind: GateKind
    source: GateSource
    sample_size: int
    notes: str = ""


SOURCE_PRIORITY = {
    GateSource.RULE_TEXT: 4,
    GateSource.ACTIVE: 3,
    GateSource.PASSIVE: 2,
    GateSource.ESTIMATE: 1,
}


def percentile_nearest_rank(values: Sequence[int], p: float) -> int | None:
    """Inclusive nearest-rank percentile. p in (0, 100]."""
    if not values:
        return None
    xs = sorted(int(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    # Nearest-rank: index = ceil(p/100 * n) - 1
    k = max(1, int((p / 100.0) * len(xs) + 0.999999)) - 1
    k = min(k, len(xs) - 1)
    return xs[k]


def infer_gate_from_survivors(
    subreddit: str,
    authors: Iterable[AuthorSample],
    *,
    percentile: float = 5.0,
    min_samples: int = 8,
) -> GateEstimate:
    """
    Passive estimate: P5 of survivor author karmas on /new (not min).
    Tiny samples degrade toward min — mark as estimate and warn (critique D7).
    """
    # Unique authors — keep max karma seen
    by_author: dict[str, int] = {}
    for a in authors:
        if not a.author or a.author in ("[deleted]", "AutoModerator"):
            continue
        by_author[a.author] = max(by_author.get(a.author, 0), int(a.karma))

    karmas = list(by_author.values())
    n = len(karmas)
    if n == 0:
        return GateEstimate(subreddit, None, GateKind.UNKNOWN, GateSource.ESTIMATE, 0, "no authors")

    gate = percentile_nearest_rank(karmas, percentile)
    if n < min_samples:
        return GateEstimate(
            subreddit,
            gate,
            GateKind.UNKNOWN,
            GateSource.ESTIMATE,
            n,
            f"sample<{min_samples}: P{percentile:.0f} ≈ noisy; treat as estimate",
        )
    return GateEstimate(
        subreddit,
        gate,
        GateKind.UNKNOWN,  # passive alone cannot tell total vs sub
        GateSource.PASSIVE,
        n,
        f"P{percentile:.0f} of {n} survivor authors",
    )


def prefer_gate(a: GateEstimate, b: GateEstimate) -> GateEstimate:
    """Higher-trust source wins."""
    if SOURCE_PRIORITY[a.source] >= SOURCE_PRIORITY[b.source]:
        return a
    return b
