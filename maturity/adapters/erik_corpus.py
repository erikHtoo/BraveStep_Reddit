"""Read Erik's SQLite corpus for gate samples / farmability research."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from maturity.config import ERIK_DB
from maturity.domain.gates import AuthorSample, GateEstimate, infer_gate_from_survivors
from maturity.domain.farmability import karma_farmability, FarmabilityScore, is_blocked


@dataclass(frozen=True)
class CorpusStats:
    posts: int
    comments: int
    subreddits: int


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or ERIK_DB)
    if not path.exists():
        raise FileNotFoundError(
            f"Erik DB not found at {path}. Run Erik scraper first or set ERIK_REDDIT_DB."
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def corpus_stats(db_path: Path | None = None) -> CorpusStats:
    conn = _connect(db_path)
    try:
        posts = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
        comments = conn.execute("SELECT COUNT(*) AS n FROM comments").fetchone()["n"]
        subs = conn.execute(
            "SELECT COUNT(DISTINCT subreddit) AS n FROM posts WHERE subreddit IS NOT NULL"
        ).fetchone()["n"]
        return CorpusStats(int(posts), int(comments), int(subs))
    finally:
        conn.close()


def authors_for_sub(subreddit: str, db_path: Path | None = None) -> list[AuthorSample]:
    """
    Build author samples from Erik posts.
    Note: scraper stores post score, not author karma — use as weak passive proxy
    and mark gate source accordingly in notes.
    """
    sub = subreddit.lstrip("r/")
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT author, MAX(score) AS score
            FROM posts
            WHERE lower(subreddit) = lower(?)
              AND author IS NOT NULL
              AND author NOT IN ('[deleted]', 'AutoModerator')
            GROUP BY author
            ORDER BY score ASC
            """,
            (sub,),
        ).fetchall()
        return [AuthorSample(author=r["author"], karma=int(r["score"] or 0)) for r in rows]
    finally:
        conn.close()


def infer_gates_from_erik(
    subreddits: list[str],
    *,
    db_path: Path | None = None,
    percentile: float = 5.0,
) -> list[GateEstimate]:
    out: list[GateEstimate] = []
    for sub in subreddits:
        authors = authors_for_sub(sub, db_path)
        est = infer_gate_from_survivors(sub, authors, percentile=percentile)
        # Annotate weakness of score-as-karma proxy
        note = est.notes + " | erik_corpus: using post score as weak karma proxy"
        out.append(
            GateEstimate(
                est.subreddit,
                est.karma_gate,
                est.gate_kind,
                est.source,
                est.sample_size,
                note,
            )
        )
    return out


def farmability_from_erik(subreddit: str, db_path: Path | None = None) -> FarmabilityScore:
    if is_blocked(subreddit):
        return karma_farmability(subreddit, avg_comment_score=0, newbie_author_share=0, gate_ease=0)

    conn = _connect(db_path)
    sub = subreddit.lstrip("r/")
    try:
        avg = conn.execute(
            """
            SELECT AVG(score) AS avg_score
            FROM comments
            WHERE post_permalink LIKE ?
            """,
            (f"%/r/{sub}/%",),
        ).fetchone()["avg_score"]
        avg_score = float(avg or 0)

        # newbie share proxy: authors whose max post score < 5
        rows = conn.execute(
            """
            SELECT author, MAX(score) AS mx
            FROM posts
            WHERE lower(subreddit) = lower(?)
            GROUP BY author
            """,
            (sub,),
        ).fetchall()
        if not rows:
            return karma_farmability(sub, avg_comment_score=avg_score, newbie_author_share=0, gate_ease=0.5)
        newbie = sum(1 for r in rows if int(r["mx"] or 0) < 5) / len(rows)
        return karma_farmability(
            sub,
            avg_comment_score=avg_score,
            newbie_author_share=newbie,
            gate_ease=0.5,
        )
    finally:
        conn.close()
