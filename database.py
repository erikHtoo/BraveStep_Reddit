"""PostgreSQL storage for scraped Reddit posts and scrape runs."""

from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb


class RedditDatabase:
    """Creates the schema and upserts Reddit posts by their immutable Reddit ID."""

    def __init__(self, database_url):
        self.connection = psycopg.connect(database_url)
        self.connection.autocommit = True

    def initialize(self):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrape_runs (
                    id UUID PRIMARY KEY,
                    target TEXT NOT NULL,
                    target_type TEXT NOT NULL CHECK (target_type IN ('subreddit', 'user')),
                    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ,
                    posts_saved INTEGER NOT NULL DEFAULT 0,
                    comments_saved INTEGER NOT NULL DEFAULT 0,
                    media_downloaded INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running'
                );

                CREATE TABLE IF NOT EXISTS posts (
                    reddit_id TEXT PRIMARY KEY,
                    subreddit TEXT,
                    title TEXT NOT NULL,
                    author TEXT,
                    permalink TEXT NOT NULL UNIQUE,
                    url TEXT,
                    selftext TEXT,
                    score INTEGER NOT NULL DEFAULT 0,
                    upvote_ratio REAL,
                    num_comments INTEGER NOT NULL DEFAULT 0,
                    num_crossposts INTEGER NOT NULL DEFAULT 0,
                    post_type TEXT,
                    is_nsfw BOOLEAN NOT NULL DEFAULT FALSE,
                    is_spoiler BOOLEAN NOT NULL DEFAULT FALSE,
                    flair TEXT,
                    total_awards INTEGER NOT NULL DEFAULT 0,
                    has_media BOOLEAN NOT NULL DEFAULT FALSE,
                    created_utc TIMESTAMPTZ,
                    raw_json JSONB NOT NULL,
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS posts_subreddit_score_idx
                    ON posts (subreddit, score DESC);
                CREATE INDEX IF NOT EXISTS posts_created_utc_idx
                    ON posts (created_utc DESC);
            """)

    def start_run(self, run_id, target, is_user):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO scrape_runs (id, target, target_type) VALUES (%s, %s, %s)",
                (run_id, target, "user" if is_user else "subreddit"),
            )

    def save_posts(self, post_pairs):
        """Upsert posts, retaining the original raw payload and refreshing live metrics."""
        if not post_pairs:
            return
        values = []
        for post, raw_post in post_pairs:
            values.append((
                post["id"], raw_post.get("subreddit"), post["title"], post["author"],
                post["permalink"], post["url"], post["selftext"], post["score"],
                post["upvote_ratio"], post["num_comments"], post["num_crossposts"],
                post["post_type"], post["is_nsfw"], post["is_spoiler"], post["flair"],
                post["total_awards"], post["has_media"], post["created_utc"], Jsonb(raw_post),
            ))
        with self.connection.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO posts (
                    reddit_id, subreddit, title, author, permalink, url, selftext, score,
                    upvote_ratio, num_comments, num_crossposts, post_type, is_nsfw,
                    is_spoiler, flair, total_awards, has_media, created_utc, raw_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (reddit_id) DO UPDATE SET
                    subreddit = EXCLUDED.subreddit,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    permalink = EXCLUDED.permalink,
                    url = EXCLUDED.url,
                    selftext = EXCLUDED.selftext,
                    score = EXCLUDED.score,
                    upvote_ratio = EXCLUDED.upvote_ratio,
                    num_comments = EXCLUDED.num_comments,
                    num_crossposts = EXCLUDED.num_crossposts,
                    post_type = EXCLUDED.post_type,
                    is_nsfw = EXCLUDED.is_nsfw,
                    is_spoiler = EXCLUDED.is_spoiler,
                    flair = EXCLUDED.flair,
                    total_awards = EXCLUDED.total_awards,
                    has_media = EXCLUDED.has_media,
                    raw_json = EXCLUDED.raw_json,
                    last_seen_at = now()
            """, values)

    def complete_run(self, run_id, posts, comments, media, status="completed"):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                UPDATE scrape_runs
                SET completed_at = now(), posts_saved = %s, comments_saved = %s,
                    media_downloaded = %s, status = %s
                WHERE id = %s
            """, (posts, comments, media, status, run_id))

    def close(self):
        self.connection.close()
