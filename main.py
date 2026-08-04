"""Command-line scraper for public Reddit posts and comments."""

import argparse
import csv
import datetime as dt
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import (
    MIRRORS,
    PROXY_URL,
    REQUEST_DELAY_SECONDS,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

POST_FIELDS = [
    "id", "title", "author", "created_utc", "permalink", "url", "score",
    "upvote_ratio", "num_comments", "num_crossposts", "selftext", "post_type",
    "is_nsfw", "is_spoiler", "flair", "total_awards", "has_media",
]
COMMENT_FIELDS = [
    "post_permalink", "comment_id", "parent_id", "author", "body", "score",
    "created_utc", "depth", "is_submitter",
]


def timestamp(value):
    return dt.datetime.fromtimestamp(value or 0, tz=dt.timezone.utc).isoformat()


def safe_target(target):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", target).strip("._") or "target"


def paths_for(target, is_user):
    prefix = "u" if is_user else "r"
    base = Path("data") / f"{prefix}_{safe_target(target)}"
    media = base / "media"
    paths = {
        "base": base,
        "posts": base / "posts.csv",
        "comments": base / "comments.csv",
        "images": media / "images",
        "videos": media / "videos",
    }
    for directory in (base, media, paths["images"], paths["videos"]):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def read_column(path, column):
    if not path.exists():
        return set()
    with path.open("r", newline="", encoding="utf-8") as handle:
        return {row.get(column, "") for row in csv.DictReader(handle) if row.get(column)}


def append_rows(path, fields, rows):
    if not rows:
        return
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def build_session(proxy_url):
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    })
    if proxy_url:
        session.proxies.update({"http": proxy_url, "https": proxy_url})
    return session


def request_json(session, url, warmup_url=None):
    last_error = None
    for attempt in range(REQUEST_RETRIES):
        try:
            if warmup_url:
                try:
                    session.get(warmup_url, timeout=REQUEST_TIMEOUT)
                except requests.RequestException:
                    pass
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 429:
                time.sleep((attempt + 1) * REQUEST_DELAY_SECONDS)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt + 1 < REQUEST_RETRIES:
                print(f"   ⚠️ Request failed: {error}. Retrying ({attempt + 2}/{REQUEST_RETRIES})...")
                time.sleep((attempt + 1) * REQUEST_DELAY_SECONDS)
    raise RuntimeError(f"Request failed for {url}: {last_error}")


def extract_post(post):
    url = post.get("url_overridden_by_dest", post.get("url", ""))
    if post.get("is_video"):
        post_type = "video"
    elif post.get("is_gallery"):
        post_type = "gallery"
    elif post.get("is_self"):
        post_type = "text"
    elif "i.redd.it" in url or url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        post_type = "image"
    else:
        post_type = "link"
    return {
        "id": post.get("id"), "title": post.get("title", ""), "author": post.get("author"),
        "created_utc": timestamp(post.get("created_utc")), "permalink": post.get("permalink"),
        "url": url, "score": post.get("score", 0), "upvote_ratio": post.get("upvote_ratio", 0),
        "num_comments": post.get("num_comments", 0), "num_crossposts": post.get("num_crossposts", 0),
        "selftext": post.get("selftext", ""), "post_type": post_type,
        "is_nsfw": post.get("over_18", False), "is_spoiler": post.get("spoiler", False),
        "flair": post.get("link_flair_text", ""), "total_awards": post.get("total_awards_received", 0),
        "has_media": bool(post.get("is_video") or post.get("is_gallery") or "i.redd.it" in url),
    }


def parse_comments(items, permalink, depth=0, max_depth=3):
    comments = []
    if depth > max_depth:
        return comments
    for item in items:
        if item.get("kind") != "t1":
            continue
        comment = item.get("data", {})
        comments.append({
            "post_permalink": permalink, "comment_id": comment.get("id"),
            "parent_id": comment.get("parent_id"), "author": comment.get("author"),
            "body": comment.get("body", ""), "score": comment.get("score", 0),
            "created_utc": timestamp(comment.get("created_utc")), "depth": depth,
            "is_submitter": comment.get("is_submitter", False),
        })
        replies = comment.get("replies")
        if isinstance(replies, dict):
            comments.extend(parse_comments(replies.get("data", {}).get("children", []), permalink, depth + 1, max_depth))
    return comments


def fetch_comments(session, permalink):
    comment_page = f"https://old.reddit.com{permalink}"
    data = request_json(session, f"{comment_page}.json?limit=100&raw_json=1", warmup_url=comment_page)
    return parse_comments(data[1].get("data", {}).get("children", []), permalink) if len(data) > 1 else []


def media_urls(post):
    urls = []
    url = post.get("url", "")
    if "i.redd.it" in url or url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        urls.append((url, "image"))
    video = post.get("media", {}).get("reddit_video", {}).get("fallback_url")
    if video:
        urls.append((video.split("?")[0], "video"))
    for image in post.get("preview", {}).get("images", []):
        source = image.get("source", {}).get("url")
        if source:
            urls.append((source.replace("&amp;", "&"), "image"))
    for item in post.get("gallery_data", {}).get("items", []):
        meta = post.get("media_metadata", {}).get(item.get("media_id"), {})
        source = meta.get("s", {}).get("u")
        if source:
            urls.append((source.replace("&amp;", "&"), "image"))
    return urls


def download_media(session, post, paths):
    downloaded = 0
    for index, (url, kind) in enumerate(media_urls(post)):
        if kind == "video" and "youtube" in url:
            continue
        suffix = ".mp4" if kind == "video" else (Path(urlparse(url).path).suffix or ".jpg")
        destination = paths["videos" if kind == "video" else "images"] / f"{post.get('id')}_{index}{suffix}"
        if destination.exists():
            continue
        try:
            with session.get(url, timeout=60, stream=True) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    shutil.copyfileobj(response.raw, handle)
            downloaded += 1
        except requests.RequestException:
            destination.unlink(missing_ok=True)
    return downloaded


def scrape(target, limit, is_user, include_comments, include_media, proxy_url):
    paths = paths_for(target, is_user)
    seen_posts = read_column(paths["posts"], "permalink")
    seen_comments = read_column(paths["comments"], "comment_id")
    session = build_session(proxy_url)
    endpoint = f"/user/{target}/submitted.json" if is_user else f"/r/{target}/new.json"
    prefix = "u" if is_user else "r"
    run_id = uuid.uuid4().hex[:8]
    started_at = time.monotonic()
    after = None
    post_count = comment_count = media_count = 0

    print("=" * 50)
    print("🤖 UNIVERSAL REDDIT SCRAPER (BraveStep_Ver0.1)")
    print("=" * 50)
    print(f"🚀 Starting FULL HISTORY scrape for {prefix}/{target}")
    print(f"   📊 Target posts: {limit}")
    print(f"   🖼️  Download media: {include_media}")
    print(f"   💬 Scrape comments: {include_comments}")
    print("   🔌 Plugins enabled: False")
    print("-" * 50)
    print("✅ CSV storage initialized")
    print(f"📋 Job started: {run_id}")

    while post_count < limit:
        payload = None
        for base_url in MIRRORS:
            query = f"{base_url}{endpoint}?limit={min(100, limit - post_count)}&raw_json=1"
            if after:
                query += f"&after={after}"
            try:
                print(f"\n📡 Fetching from: {base_url}")
                warmup_url = None
                if not after and base_url == "https://old.reddit.com":
                    target_type = "user" if is_user else "r"
                    warmup_url = f"{base_url}/{target_type}/{target}/"
                payload = request_json(session, query, warmup_url=warmup_url)
                print(f"   Found {len(payload.get('data', {}).get('children', []))} posts in this batch")
                break
            except RuntimeError as error:
                print(f"   ⚠️ Error with {base_url}: {error}")
        if not payload:
            break

        children = payload.get("data", {}).get("children", [])
        if not children:
            break
        rows = []
        comment_rows = []
        for child in children:
            raw_post = child.get("data", {})
            post = extract_post(raw_post)
            permalink = post.get("permalink")
            if not permalink or permalink in seen_posts:
                continue
            rows.append(post)
            seen_posts.add(permalink)
            if include_comments and post["num_comments"]:
                try:
                    comments = fetch_comments(session, permalink)
                    new_comments = [comment for comment in comments if comment["comment_id"] not in seen_comments]
                    comment_rows.extend(new_comments)
                    seen_comments.update(comment["comment_id"] for comment in new_comments)
                except RuntimeError as error:
                    print(f"Could not fetch comments for {post['id']}: {error}")
            if include_media:
                media_count += download_media(session, raw_post, paths)

        append_rows(paths["posts"], POST_FIELDS, rows)
        append_rows(paths["comments"], COMMENT_FIELDS, comment_rows)
        # Also write SQLite so maturity gates can read the same corpus
        if rows and not is_user:
            try:
                from sqlite_store import save_comments, save_posts

                db_posts = save_posts(rows, target)
                by_permalink = {p.get("permalink") or "": p.get("id") or "" for p in rows}
                db_comments = save_comments(comment_rows, by_permalink) if comment_rows else 0
                print(f"   🗄️  SQLite: +{db_posts} posts, +{db_comments} comments")
            except Exception as db_err:
                print(f"   ⚠️ SQLite save failed (CSV still ok): {db_err}")
        post_count += len(rows)
        comment_count += len(comment_rows)
        if rows:
            print(f"✅ Saved {len(rows)} new posts")
        else:
            print("💤 No new unique posts found.")
        print(f"\n📊 Progress: {post_count}/{limit} posts")
        print(f"   🖼️  Images/Videos: {media_count}")
        print(f"   💬 Comments: {comment_count}")
        after = payload.get("data", {}).get("after")
        if not after or not rows:
            break
        print(f"\n⏸️ Cooling down ({REQUEST_DELAY_SECONDS:g}s)...")
        time.sleep(REQUEST_DELAY_SECONDS)

    duration = time.monotonic() - started_at
    print(f"✅ Job {run_id} completed: {post_count} posts, {comment_count} comments in {duration:.1f}s")
    print("\n" + "=" * 50)
    print("✅ SCRAPE COMPLETE!")
    print(f"   📁 Data saved to: {paths['base']}")
    print(f"   📊 Total posts: {post_count}")
    print(f"   🖼️  Total media files: {media_count}")
    print(f"   💬 Total comments: {comment_count}")
    print(f"   ⏱️  Duration: {duration:.1f}s")


def main():
    parser = argparse.ArgumentParser(description="Scrape public Reddit posts and comments to CSV.")
    parser.add_argument("target", help="Subreddit or Reddit username to scrape")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of new posts (default: 100)")
    parser.add_argument("--user", action="store_true", help="Treat target as a Reddit username")
    parser.add_argument("--no-comments", action="store_true", help="Do not fetch comments")
    parser.add_argument("--no-media", action="store_true", help="Do not download media")
    parser.add_argument("--proxy", default=PROXY_URL, help="Optional HTTP(S) proxy URL")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    scrape(args.target, args.limit, args.user, not args.no_comments, not args.no_media, args.proxy)


if __name__ == "__main__":
    main()
