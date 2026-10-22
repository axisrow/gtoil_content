#!/usr/bin/env python3
"""Collect fresh news from RSS feeds in config/sources.yaml into inbox/news/YYYY-MM-DD.json."""
import argparse
import calendar
import json
import re
import time
from datetime import datetime, timezone

import feedparser
import yaml

from common import ROOT

SOURCES = ROOT / "config" / "sources.yaml"
INBOX = ROOT / "inbox" / "news"


def clean(html: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()[:limit]


def entry_ts(e) -> float | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    return calendar.timegm(t) if t else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=48, help="max age of items")
    args = ap.parse_args()

    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    keywords = [k.lower() for k in cfg.get("keywords", [])]
    exclude = [k.lower() for k in cfg.get("exclude", [])]
    cutoff = time.time() - args.hours * 3600

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    INBOX.mkdir(parents=True, exist_ok=True)
    out = INBOX / f"{today}.json"
    items = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    seen = {i["url"] for i in items}

    for feed in cfg["feeds"]:
        parsed = feedparser.parse(feed["url"])
        if parsed.bozo and not parsed.entries:
            print(f"! {feed['name']}: {parsed.bozo_exception}")
            continue
        added = 0
        for e in parsed.entries:
            url, ts = e.get("link"), entry_ts(e)
            if not url or url in seen or (ts and ts < cutoff):
                continue
            title, summary = clean(e.get("title", ""), 300), clean(e.get("summary", ""))
            text = f"{title} {summary}".lower()
            if feed.get("filter") and keywords and not any(k in text for k in keywords):
                continue
            if any(k in text for k in exclude):
                continue
            items.append({
                "title": title,
                "url": url,
                "source": feed["name"],
                "published": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                "summary": summary,
            })
            seen.add(url)
            added += 1
        print(f"{feed['name']}: +{added}")

    items.sort(key=lambda i: i["published"] or "", reverse=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(items)} items")


if __name__ == "__main__":
    main()
