"""Runtime configuration for the Reddit scraper."""

import os
from pathlib import Path


def load_env_file() -> None:
    """Load simple KEY=VALUE entries from a local .env file when present."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
)
PROXY_URL = os.getenv("PROXY_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
REQUEST_RETRIES = int(os.getenv("REQUEST_RETRIES", "3"))
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))

# The first endpoint is preferred; mirrors are fallbacks when it is unavailable.
MIRRORS = [
    "https://old.reddit.com",
    "https://redlib.privadency.com",
    "https://redlib.orangenet.cc",
    "https://red.artemislena.eu",
]
