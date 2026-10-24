#!/usr/bin/env python3
"""Collect new article links from competitors' article sections into inbox/competitors/YYYY-MM-DD.json.

Per competitor (config/competitors.yaml), sources are tried in order until one yields links:
  1. `rss`      — the site's own feed;
  2. `articles` — links found in the HTML of the articles section;
  3. sitemap    — URLs under the articles section path, from robots.txt `Sitemap:` or /sitemap.xml
                  (for sections that render their list with JavaScript).
`keywords` (optional) keeps only titles containing one of the words.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse

import feedparser
import yaml

from common import ROOT

CONFIG = ROOT / "config" / "competitors.yaml"
INBOX = ROOT / "inbox" / "competitors"
UA = "Mozilla/5.0 (compatible; gtoil-content-bot/1.0)"
MAX_CHILD_SITEMAPS = 30


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            a = dict(attrs)
            self._href, self._label, self._text = a.get("href"), a.get("title") or a.get("aria-label") or "", []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            text = re.sub(r"\s+", " ", "".join(self._text)).strip()
            self.links.append((self._href, text if len(text) >= len(self._label) else self._label))
            self._href = None


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")


def slug_title(url: str) -> str:
    """Readable title from the last URL segment, for links without anchor text."""
    seg = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
    return re.sub(r"\.(html?|php)$", "", seg).replace("-", " ").replace("_", " ").strip()


PAGINATION = re.compile(r"/(browse|page)/\d+(\.html?)?/?$|[?&]page=\d+")
TEASER_META = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{4}\s+(\d+\s*min\s+)?", re.I)  # "10/22/2026 5min "


def clean(links: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop pagination links and letterless titles ("2"), strip date/read-time prefixes."""
    out = []
    for url, title in links:
        title = TEASER_META.sub("", title).strip()
        if PAGINATION.search(url) or not re.search(r"[^\W\d_]", title):
            continue
        out.append((url, title))
    return out


def in_section(url: str, section: str) -> bool:
    """URL is an article below the section: /useful/ → /useful/x.html, /tips.html → /tips/x.html."""
    u, s = urlparse(url), urlparse(section)
    base = re.sub(r"\.(html?|php)$", "", s.path).rstrip("/")
    return u.netloc == s.netloc and u.path.startswith(base + "/") and u.path.rstrip("/") != base


def from_rss(feed_url: str) -> list[tuple[str, str]]:
    parsed = feedparser.parse(feed_url, agent=UA)
    return [(e.link, e.get("title", "").strip() or slug_title(e.link)) for e in parsed.entries if e.get("link")]


def from_html(section: str) -> list[tuple[str, str]]:
    parser = LinkParser()
    parser.feed(get(section))
    found = {}
    for href, text in parser.links:
        url = urljoin(section, href).split("#")[0]
        if in_section(url, section):
            title = text if len(text) >= 20 else found.get(url) or slug_title(url)
            if len(title) > len(found.get(url, "")):
                found[url] = title[:300]
    return list(found.items())


def sitemap_urls(section: str) -> list[str]:
    root = f"{urlparse(section).scheme}://{urlparse(section).netloc}"
    try:
        maps = re.findall(r"(?im)^sitemap:\s*(\S+)", get(f"{root}/robots.txt")) or [f"{root}/sitemap.xml"]
    except Exception:
        maps = [f"{root}/sitemap.xml"]
    urls, queue, seen = [], list(maps), set()
    while queue and len(seen) < MAX_CHILD_SITEMAPS:
        m = queue.pop(0)
        if m in seen:
            continue
        seen.add(m)
        try:
            tree = ET.fromstring(get(m).encode())
        except Exception:
            continue
        locs = [el.text.strip() for el in tree.iter() if el.tag.endswith("loc") and el.text]
        if tree.tag.endswith("sitemapindex"):
            queue += locs
        else:
            urls += locs
    return urls


def from_sitemap(section: str) -> list[tuple[str, str]]:
    return [(u, slug_title(u)) for u in dict.fromkeys(sitemap_urls(section)) if in_section(u, section)]


def collect(c: dict) -> tuple[str, list[tuple[str, str]]]:
    tried = []
    for method, src in (("rss", c.get("rss")), ("html", c.get("articles")), ("sitemap", c.get("articles"))):
        if not src:
            continue
        try:
            links = {"rss": from_rss, "html": from_html, "sitemap": from_sitemap}[method](src)
        except Exception as e:  # one dead source must not stop the rest
            tried.append(f"{method}: {e}")
            continue
        if links:
            return method, links
        tried.append(f"{method}: 0")
    raise RuntimeError("; ".join(tried) or "no source configured")


def main() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    competitors = [c for group in ("asian", "russian", "international") for c in cfg.get(group, [])
                   if c.get("articles") or c.get("rss")]

    INBOX.mkdir(parents=True, exist_ok=True)
    seen = {i["url"] for f in INBOX.glob("*.json") for i in json.loads(f.read_text(encoding="utf-8"))}
    out = INBOX / f"{datetime.now(timezone.utc):%Y-%m-%d}.json"
    items = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []

    for c in competitors:
        try:
            method, links = collect(c)
        except Exception as e:
            print(f"! {c['name']}: {e}")
            continue
        keywords = [k.lower() for k in c.get("keywords", [])]
        links = clean(links)
        relevant = [(u, t) for u, t in links if not keywords or any(k in t.lower() for k in keywords)]
        new = [(u, t) for u, t in relevant if u not in seen]
        for url, title in new:
            items.append({"competitor": c["name"], "title": title, "url": url})
            seen.add(url)
        print(f"{c['name']} [{method}]: {len(links)} links, {len(relevant)} relevant, +{len(new)} new")

    out.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(items)} items")


if __name__ == "__main__":
    main()
