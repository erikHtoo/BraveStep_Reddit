"""Shared config for the maturity package."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Erik listening corpus (optional join)
# Supports: sibling `../erik-reddit` OR nested inside that repo as `maturity/`
_parent = BASE_DIR.parent
if (_parent / "main.py").exists() and (_parent / "export").is_dir():
    ERIK_REPO = _parent
else:
    ERIK_REPO = _parent / "erik-reddit"
ERIK_DB = Path(os.getenv("ERIK_REDDIT_DB", str(ERIK_REPO / "data" / "reddit_scraper.db")))

# Secrets — never commit real values
SOCIAVAULT_KEY = os.getenv("SOCIAVAULT_KEY", "")
SOCIAVAULT_BASE = os.getenv("SOCIAVAULT_BASE", "https://api.sociavault.com/v1")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "bravestep-maturity:v0.1 (by /u/bravestep-lab)",
)
REDDIT_REDIRECT_URI = os.getenv("REDDIT_OAUTH_REDIRECT", "http://localhost:8100/oauth/callback")
REDDIT_TOKEN_URL = os.getenv(
    "REDDIT_TOKEN_URL",
    "https://www.reddit.com/api/v1/access_token",
)
REDDIT_AUTH_URL = "https://www.reddit.com/api/v1/authorize"

# AES keyring placeholder — prod must set CHANNEL_TOKEN_ENCRYPTION_KEYS=v1:<b64-32B>
CHANNEL_TOKEN_ENCRYPTION_KEYS = os.getenv("CHANNEL_TOKEN_ENCRYPTION_KEYS", "")

# Lab-only plaintext tokens (NEVER in prod)
ALLOW_PLAINTEXT_TOKENS = os.getenv("MATURITY_ALLOW_PLAINTEXT_TOKENS", "0") in ("1", "true", "yes")

GATE_PERCENTILE = 5  # P5 survivors — matches Bravestep reddit_gate_inference
OUTCOME_MAX_INFLUENCE = 0.15

API_HOST = os.getenv("MATURITY_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("MATURITY_API_PORT", "8100"))
