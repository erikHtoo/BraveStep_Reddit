"""Seven draft guardrails — hard block before human submit."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence
from urllib.parse import urlparse


class ViolationKind(str, Enum):
    REPOST = "repost"
    DUP_COMMENT = "dup_comment"
    SHORTENER = "shortener"
    FLOOD = "flood"
    MISSING_DISCLOSURE = "missing_disclosure"
    ASTROTURF = "astroturf"
    SHADOWBAN = "shadowban"


SHORTENER_HOSTS = frozenset(
    {
        "bit.ly",
        "t.co",
        "tinyurl.com",
        "goo.gl",
        "ow.ly",
        "buff.ly",
        "rebrand.ly",
        "cutt.ly",
        "is.gd",
    }
)

DISCLOSURE_PATTERNS = (
    re.compile(r"\bfull disclosure\b", re.I),
    re.compile(r"\bi (built|made|created|founded)\b", re.I),
    re.compile(r"\bmy (app|tool|product|startup|saas)\b", re.I),
    re.compile(r"\bop here\b", re.I),
    re.compile(r"\bi'?m the (founder|maker|creator)\b", re.I),
)

URL_RE = re.compile(r"https?://[^\s)]+", re.I)


@dataclass(frozen=True)
class Draft:
    text: str
    canonical_link: str | None = None
    is_promo: bool = False
    account_ids_involved: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoryItem:
    text: str
    canonical_link: str | None = None


@dataclass(frozen=True)
class RateState:
    actions_last_hour: int = 0
    actions_last_day: int = 0
    hour_limit: int = 6
    day_limit: int = 20
    shadowbanned: bool = False


@dataclass(frozen=True)
class GuardrailResult:
    violations: tuple[ViolationKind, ...]
    block: bool


def _canonical_link(url: str | None) -> str | None:
    if not url:
        return None
    try:
        p = urlparse(url.strip())
        host = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").rstrip("/")
        return f"{host}{path}"
    except Exception:
        return url.strip().lower()


def _hosts_in_text(text: str) -> set[str]:
    hosts: set[str] = set()
    for m in URL_RE.finditer(text or ""):
        try:
            host = urlparse(m.group(0)).netloc.lower().removeprefix("www.")
            if host:
                hosts.add(host)
        except Exception:
            continue
    return hosts


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def check_action(draft: Draft, history: Sequence[HistoryItem], rate: RateState) -> GuardrailResult:
    v: list[ViolationKind] = []

    if rate.shadowbanned:
        v.append(ViolationKind.SHADOWBAN)

    if len(set(draft.account_ids_involved)) > 1:
        v.append(ViolationKind.ASTROTURF)

    hosts = _hosts_in_text(draft.text)
    if hosts & SHORTENER_HOSTS:
        v.append(ViolationKind.SHORTENER)

    if rate.actions_last_hour >= rate.hour_limit or rate.actions_last_day >= rate.day_limit:
        v.append(ViolationKind.FLOOD)

    link = _canonical_link(draft.canonical_link)
    if link:
        prior_links = {_canonical_link(h.canonical_link) for h in history}
        if link in prior_links:
            v.append(ViolationKind.REPOST)

    norm = _norm_text(draft.text)
    if norm and any(_norm_text(h.text) == norm for h in history):
        v.append(ViolationKind.DUP_COMMENT)

    if draft.is_promo:
        if not any(p.search(draft.text or "") for p in DISCLOSURE_PATTERNS):
            v.append(ViolationKind.MISSING_DISCLOSURE)

    # dedupe while preserving order
    seen: set[ViolationKind] = set()
    uniq: list[ViolationKind] = []
    for x in v:
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return GuardrailResult(tuple(uniq), block=bool(uniq))
