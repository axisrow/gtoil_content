#!/usr/bin/env python3
"""Collect new article links from competitors' article sections into inbox/competitors/YYYY-MM-DD.json."""
import json
import re
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import yaml

from common import ROOT

CONFIG = ROOT / "config" / "competitors.yaml"
INBOX = ROOT / "inbox" / "competitors"
UA = "Mozilla/5.0 (compatible; gtoil-content-bot/1.0)"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._text = dict(attrs).get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, re.sub(r"\s+", " ", "".join(self._text)).strip()))
            self._href = None


def article_links(section: str) -> list[tuple[str, str]]:
    req = urllib.request.Request(section, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
    parser = LinkParser()
    parser.feed(html)
    base = urlparse(section)
    found = {}
    for href, text in parser.links:
        url = urljoin(section, href).split("#")[0]
        u = urlparse(url)
        # same host, inside the articles section, deeper than the section itself, with a real title
        if u.netloc == base.netloc and u.path.startswith(base.path) and u.path.rstrip("/") != base.path.rstrip("/") \
                and len(text) >= 20:
            found.setdefault(url, text[:300])
    return [(u, t) for u, t in found.items()]


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    competitors = [c for group in ("asian", "russian", "international") for c in cfg.get(group, []) if c.get("articles")]

    INBOX.mkdir(parents=True, exist_ok=True)
    seen = {i["url"] for f in INBOX.glob("*.json") for i in json.loads(f.read_text(encoding="utf-8"))}
    out = INBOX / f"{datetime.now(timezone.utc):%Y-%m-%d}.json"
    items = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []

    for c in competitors:
        try:
            links = article_links(c["articles"])
        except Exception as e:  # one dead site must not stop the rest
            print(f"! {c['name']}: {e}")
            continue
        new = [(u, t) for u, t in links if u not in seen]
        for url, title in new:
            items.append({"competitor": c["name"], "title": title, "url": url})
            seen.add(url)
        print(f"{c['name']}: {len(links)} links, +{len(new)} new")

    out.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(items)} items")


if __name__ == "__main__":
    main()
