"""Reddit user OAuth + health reads (/me, /me/karma)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from maturity.config import (
    REDDIT_AUTH_URL,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_REDIRECT_URI,
    REDDIT_TOKEN_URL,
    REDDIT_USER_AGENT,
)


class RedditOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str


@dataclass(frozen=True)
class MeProfile:
    name: str
    verified_email: bool
    total_karma: int
    link_karma: int
    comment_karma: int
    created_utc: float


def _require_app() -> None:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise RedditOAuthError(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET required (Reddit 'web app')"
        )


def build_authorize_url(*, state: str | None = None, scopes: str = "identity read history mysubreddits") -> tuple[str, str]:
    """Returns (url, state)."""
    _require_app()
    st = state or secrets.token_urlsafe(24)
    q = urlencode(
        {
            "client_id": REDDIT_CLIENT_ID,
            "response_type": "code",
            "state": st,
            "redirect_uri": REDDIT_REDIRECT_URI,
            "duration": "permanent",
            "scope": scopes,
        }
    )
    return f"{REDDIT_AUTH_URL}?{q}", st


def exchange_code(code: str) -> TokenSet:
    _require_app()
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            REDDIT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDDIT_REDIRECT_URI,
            },
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            headers={"User-Agent": REDDIT_USER_AGENT},
        )
    if r.status_code >= 400:
        raise RedditOAuthError(f"token exchange failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=int(data.get("expires_in") or 0),
        scope=str(data.get("scope") or ""),
    )


def refresh_token(refresh: str) -> TokenSet:
    _require_app()
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            REDDIT_TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": refresh},
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            headers={"User-Agent": REDDIT_USER_AGENT},
        )
    if r.status_code >= 400:
        raise RedditOAuthError(f"refresh failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh),
        expires_in=int(data.get("expires_in") or 0),
        scope=str(data.get("scope") or ""),
    )


def _oauth_get(access_token: str, path: str) -> Any:
    url = f"https://oauth.reddit.com{path}"
    with httpx.Client(timeout=30.0) as client:
        r = client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": REDDIT_USER_AGENT,
            },
        )
    if r.status_code >= 400:
        raise RedditOAuthError(f"GET {path} failed: {r.status_code} {r.text[:300]}")
    return r.json()


def fetch_me(access_token: str) -> MeProfile:
    data = _oauth_get(access_token, "/api/v1/me")
    return MeProfile(
        name=str(data.get("name") or ""),
        verified_email=bool(data.get("has_verified_email")),
        total_karma=int(data.get("total_karma") or 0),
        link_karma=int(data.get("link_karma") or 0),
        comment_karma=int(data.get("comment_karma") or 0),
        created_utc=float(data.get("created_utc") or 0),
    )


def fetch_me_karma(access_token: str) -> dict[str, dict[str, int]]:
    """
    Returns {subreddit: {comment_karma, link_karma}} from /api/v1/me/karma
    """
    data = _oauth_get(access_token, "/api/v1/me/karma")
    out: dict[str, dict[str, int]] = {}
    rows = data.get("data") if isinstance(data, dict) else data
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            sr = str(row.get("sr") or row.get("subreddit") or "")
            if not sr:
                continue
            out[sr] = {
                "comment_karma": int(row.get("comment_karma") or 0),
                "link_karma": int(row.get("link_karma") or 0),
            }
    return out
