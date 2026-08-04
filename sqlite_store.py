"""Minimal SQLite corpus for maturity gates (alongside Erik CSV output)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "reddit_scraper.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT,
    title TEXT,
    author TEXT,
    created_utc TEXT,
    permalink TEXT UNIQUE,
    url TEXT,
    score INTEGER DEFAULT 0,
    upvote_ratio REAL DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    num_crossposts INTEGER DEFAULT 0,
    selftext TEXT,
    post_type TEXT,
    is_nsfw INTEGER DEFAULT 0,
    is_spoiler INTEGER DEFAULT 0,
    flair TEXT,
    total_awards INTEGER DEFAULT 0,
    has_media INTEGER DEFAULT 0,
    media_downloaded INTEGER DEFAULT 0,
    source TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT UNIQUE,
    post_id TEXT,
    post_permalink TEXT,
    parent_id TEXT,
    author TEXT,
    body TEXT,
    score INTEGER DEFAULT 0,
    created_utc TEXT,
    depth INTEGER DEFAULT 0,
    is_submitter INTEGER DEFAULT 0,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subreddits (
    name TEXT PRIMARY KEY,
    last_scraped TEXT,
    total_posts INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0
);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def save_posts(posts: list[dict], subreddit: str, *, source: str = "History-Full") -> int:
    if not posts:
        return 0
    conn = connect()
    saved = 0
    try:
        for post in posts:
            pid = post.get("id") or ""
            if not pid:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO posts (
                    id, subreddit, title, author, created_utc, permalink, url, score,
                    upvote_ratio, num_comments, num_crossposts, selftext, post_type,
                    is_nsfw, is_spoiler, flair, total_awards, has_media, media_downloaded, source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    pid,
                    subreddit,
                    post.get("title") or "",
                    post.get("author") or "",
                    post.get("created_utc") or "",
                    post.get("permalink") or "",
                    post.get("url") or "",
                    int(post.get("score") or 0),
                    float(post.get("upvote_ratio") or 0),
                    int(post.get("num_comments") or 0),
                    int(post.get("num_crossposts") or 0),
                    post.get("selftext") or "",
                    post.get("post_type") or "text",
                    1 if post.get("is_nsfw") else 0,
                    1 if post.get("is_spoiler") else 0,
                    post.get("flair") or "",
                    int(post.get("total_awards") or 0),
                    1 if post.get("has_media") else 0,
                    0,
                    source,
                ),
            )
            saved += 1
        conn.execute(
            """
            INSERT INTO subreddits(name, last_scraped, total_posts, total_comments)
            VALUES (?, datetime('now'), ?, 0)
            ON CONFLICT(name) DO UPDATE SET
              last_scraped=excluded.last_scraped,
              total_posts=(SELECT COUNT(*) FROM posts WHERE lower(subreddit)=lower(excluded.name))
            """,
            (subreddit, saved),
        )
        conn.commit()
    finally:
        conn.close()
    return saved


def save_comments(comments: list[dict], post_id_by_permalink: dict[str, str]) -> int:
    if not comments:
        return 0
    conn = connect()
    saved = 0
    try:
        for comment in comments:
            cid = comment.get("comment_id") or ""
            if not cid:
                continue
            permalink = comment.get("post_permalink") or ""
            post_id = post_id_by_permalink.get(permalink, "")
            conn.execute(
                """
                INSERT OR IGNORE INTO comments (
                    comment_id, post_id, post_permalink, parent_id, author, body,
                    score, created_utc, depth, is_submitter
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    cid,
                    post_id,
                    permalink,
                    comment.get("parent_id"),
                    comment.get("author"),
                    comment.get("body"),
                    int(comment.get("score") or 0),
                    comment.get("created_utc"),
                    int(comment.get("depth") or 0),
                    1 if comment.get("is_submitter") else 0,
                ),
            )
            if conn.total_changes:
                saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved
