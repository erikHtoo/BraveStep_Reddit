#!/usr/bin/env python3
"""Import data/r_*/posts.csv into SQLite when live scrape 403s but CSV exists."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlite_store import save_posts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to posts.csv")
    parser.add_argument("--sub", required=True, help="Subreddit name")
    args = parser.parse_args()
    path = Path(args.csv)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    posts = []
    for row in rows:
        if not (row.get("id") or "").strip():
            continue
        posts.append(
            {
                "id": row.get("id") or "",
                "title": row.get("title") or "",
                "author": row.get("author") or "",
                "created_utc": row.get("created_utc") or "",
                "permalink": row.get("permalink") or "",
                "url": row.get("url") or "",
                "score": int(float(row.get("score") or 0)),
                "upvote_ratio": float(row.get("upvote_ratio") or 0),
                "num_comments": int(float(row.get("num_comments") or 0)),
                "num_crossposts": int(float(row.get("num_crossposts") or 0)),
                "selftext": row.get("selftext") or "",
                "post_type": row.get("post_type") or "text",
                "is_nsfw": str(row.get("is_nsfw", "")).lower() in ("1", "true", "yes"),
                "is_spoiler": str(row.get("is_spoiler", "")).lower() in ("1", "true", "yes"),
                "flair": row.get("flair") or "",
                "total_awards": int(float(row.get("total_awards") or 0)),
                "has_media": str(row.get("has_media", "")).lower() in ("1", "true", "yes"),
            }
        )
    n = save_posts(posts, args.sub.lstrip("r/"), source="csv_import")
    print(f"imported {n} posts into SQLite for r/{args.sub.lstrip('r/')}")


if __name__ == "__main__":
    main()
