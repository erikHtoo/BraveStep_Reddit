"""SociaVault adapter — prod listening path for gate samples / search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from maturity.config import SOCIAVAULT_BASE, SOCIAVAULT_KEY
from maturity.domain.gates import AuthorSample


@dataclass(frozen=True)
class VaultPost:
    id: str
    subreddit: str
    author: str
    score: int
    title: str
    url: str


class SociaVaultError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not SOCIAVAULT_KEY:
        raise SociaVaultError("SOCIAVAULT_KEY is not set")
    # Docs: X-API-Key only (https://docs.sociavault.com)
    return {
        "X-API-Key": SOCIAVAULT_KEY,
        "Accept": "application/json",
    }


def _as_list(payload: Any) -> list[dict]:
    """Normalize SociaVault shapes → list[dict].

    Observed: { success, data: { posts: { "0": {...}, "1": {...} }, after } }
    Also accept list or data/posts/results/items arrays.
    """
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    # Unwrap top-level data envelope once or twice
    candidates: list[Any] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.append(data)
        inner = data.get("data")
        if isinstance(inner, dict):
            candidates.append(inner)
    elif isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        for key in ("posts", "results", "items", "comments"):
            v = obj.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
            if isinstance(v, dict):
                # numeric-keyed object: {"0": {...}, "1": {...}}
                vals = list(v.values())
                if vals and all(isinstance(x, dict) for x in vals):
                    return vals  # type: ignore[return-value]
    return []


def search_posts(query: str, *, limit: int = 25) -> list[VaultPost]:
    url = f"{SOCIAVAULT_BASE}/scrape/reddit/search"
    with httpx.Client(timeout=45.0) as client:
        r = client.get(url, headers=_headers(), params={"query": query})
    if r.status_code >= 400:
        raise SociaVaultError(f"search failed HTTP {r.status_code}: {r.text[:300]}")
    out: list[VaultPost] = []
    for row in _as_list(r.json())[:limit]:
        out.append(
            VaultPost(
                id=str(row.get("id") or row.get("post_id") or ""),
                subreddit=str(row.get("subreddit") or row.get("subreddit_name") or ""),
                author=str(row.get("author") or row.get("author_name") or ""),
                score=int(row.get("score") or row.get("ups") or 0),
                title=str(row.get("title") or ""),
                url=str(row.get("url") or row.get("permalink") or ""),
            )
        )
    return out


def subreddit_new_authors(subreddit: str, *, limit: int = 50) -> list[AuthorSample]:
    """
    /new-style listing for gate P5 via SociaVault.
    1 credit / request. Fail loud if empty after 200.
    """
    sub = subreddit.lstrip("r/")
    url = f"{SOCIAVAULT_BASE}/scrape/reddit/subreddit"
    url2 = f"{SOCIAVAULT_BASE}/scrape/reddit/subreddit/search"

    with httpx.Client(timeout=45.0) as client:
        r = client.get(
            url,
            headers=_headers(),
            params={"subreddit": sub, "sort": "new", "timeframe": "week", "trim": "true"},
        )
        if r.status_code >= 400:
            r = client.get(
                url2,
                headers=_headers(),
                params={"subreddit": sub, "query": "a", "trim": "true"},
            )
            if r.status_code >= 400:
                raise SociaVaultError(
                    f"subreddit listing failed HTTP {r.status_code}: {r.text[:300]}"
                )

        rows = _as_list(r.json())
        credits = None
        try:
            credits = r.json().get("credits_used")
        except Exception:
            pass

    authors: list[AuthorSample] = []
    seen: set[str] = set()
    for row in rows:
        author = str(row.get("author") or row.get("author_name") or "")
        if not author or author in ("[deleted]", "AutoModerator") or author in seen:
            continue
        seen.add(author)
        karma = row.get("author_karma") or row.get("author_total_karma") or row.get("score") or 0
        authors.append(AuthorSample(author=author, karma=int(karma)))
        if len(authors) >= limit:
            break

    if not authors:
        raise SociaVaultError(f"empty listing for r/{sub} — fail loud, do not invent gates")

    # stash credits on first sample via notes? return plain list; bake-off logs separately
    _ = credits
    return authors
