#!/usr/bin/env python3
"""Mechanics for posting published articles to social networks; the browser part is the Claude Code session's job (/oil:social, /browser-use).

  social.py plan --to vk,x           print what to post: rendered texts, compose urls, instructions
  social.py done <slug> <net> <url>  record a successful post in content/social.json
  social.py status                   show networks from config/social.yaml
  social.py send [net] [--dry-run]   send next unposted article via Bot API (networks with mode: bot)
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

from common import ROOT, read_frontmatter, slug_of

CONFIG = ROOT / "config" / "social.yaml"
POSTS = ROOT / "docs" / "blog" / "posts"
LEDGER = ROOT / "content" / "social.json"


def load_networks() -> dict[str, dict]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return {key: {**cfg.get("defaults", {}), **net} for key, net in cfg["networks"].items()}


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}


def save_ledger(ledger: dict) -> None:
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def post_url(meta: dict, slug: str) -> str:
    """Site URL of a post, per `post_url_format: "{date}/{slug}"` in mkdocs.yml.

    The slug lives in the file name (mkdocs blog derives it from there, promote.py
    guarantees it's latin); front-matter carries no slug.
    """
    site = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))["site_url"].rstrip("/")
    date = str(meta["date"])[:10].replace("-", "/")
    return f"{site}/blog/{date}/{slug}/"


def hashtags(tags: list[str], limit: int) -> str:
    tags = (re.sub(r"\W", "", re.sub(r"[\s-]+", "_", t)) for t in tags[:limit])
    return " ".join(f"#{t}" for t in tags if t)


def render(meta: dict, net: dict, slug: str) -> str:
    fields = {
        "title": meta["title"],
        "summary": " ".join(meta["summary"].split()),
        "url": post_url(meta, slug),
        "hashtags": hashtags(meta.get("tags", []), net["hashtags"]),
    }

    def fmt() -> str:
        return re.sub(r"\n{3,}", "\n\n", net["template"].format(**fields)).strip()

    def size(text: str) -> int:
        # X and the like count any link as a fixed number of characters
        return len(text.replace(fields["url"], "x" * net["url_len"])) if net.get("url_len") else len(text)

    text, limit = fmt(), net.get("max_len")
    if limit and size(text) > limit:
        # trim the summary first, then drop hashtags; title and link stay intact
        keep = len(fields["summary"]) - (size(text) - limit) - 1
        fields["summary"] = fields["summary"][:keep].rstrip() + "…" if keep > 0 else ""
        text = fmt()
    if limit and size(text) > limit:
        fields["hashtags"] = ""
        text = fmt()
    if limit and size(text) > limit:
        raise ValueError(f"{size(text)} > max_len {limit} even with title and link only; shorten the template")
    return text


def pick_posts(args, ledger: dict, targets: list[str]) -> list[Path]:
    if args.posts:
        return [Path(p).resolve() for p in args.posts]
    files = sorted(POSTS.glob("*.md"))
    if not files:
        return []
    date = args.date or max(f.name[:10] for f in files)
    picked = [f for f in files if f.name.startswith(date)]
    if not args.force:
        picked = [f for f in picked if any(t not in ledger.get(slug_of(f), {}) for t in targets)]
    return picked[: args.limit] if args.limit else picked


def cmd_plan(args, networks: dict) -> None:
    targets = args.to.split(",") if args.to else [k for k, n in networks.items() if n.get("enabled")]
    unknown = [t for t in targets if t not in networks]
    if unknown:
        sys.exit(f"unknown networks: {', '.join(unknown)} (see config/social.yaml)")
    if not targets:
        sys.exit("no networks: pass --to vk,x or set enabled: true in config/social.yaml")

    ledger = load_ledger()
    posts = pick_posts(args, ledger, targets)
    if not posts:
        print("nothing to post")
        return
    for path in posts:
        meta, _ = read_frontmatter(path)
        slug = slug_of(path)
        for key in targets:
            if key in ledger.get(slug, {}) and not args.force:
                continue
            net = networks[key]
            print(f"=== {slug} | {key} | {net['name']}")
            print(f"compose: {net['compose_url']}")
            print(f"domains: {', '.join(net.get('domains') or [])}")
            print(f"instructions: {net['instructions'].strip()}")
            print(f"<<<POST\n{render(meta, net, slug)}\nPOST>>>\n")


def cmd_done(args, networks: dict) -> None:
    if args.network not in networks:
        sys.exit(f"unknown network {args.network!r}; known: {', '.join(networks)}")
    ledger = load_ledger()
    ledger.setdefault(args.slug, {})[args.network] = {
        "url": args.url,
        "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_ledger(ledger)
    print(f"recorded: {args.slug} → {args.network} {args.url}")


def cmd_status(networks: dict) -> None:
    for key, net in networks.items():
        print(f"{key:10} {'enabled ' if net.get('enabled') else 'disabled'}  {net['compose_url']}")


def tg_send(token: str, chat: str, text: str) -> dict:
    """Bot API sendMessage. One retry on 429 with small retry_after.

    ponytail: no send queue and no backoff ladder — one shot fits 5 posts/day;
    add a queue when a network starts demanding more.
    """
    payload = urlencode({"chat_id": chat, "text": text}).encode()
    body: dict = {}
    for attempt in (1, 2):
        req = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=payload)
        try:
            with urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except HTTPError as e:
            body = json.loads(e.read())
        if body.get("ok"):
            return body["result"]
        wait = (body.get("parameters") or {}).get("retry_after")
        if not wait or wait > 60:
            break
        time.sleep(wait + 1)
    sys.exit(f"sendMessage failed: {body.get('description')}")


def cmd_send(args, networks: dict) -> None:
    net = networks.get(args.network)
    if net is None:
        sys.exit(f"unknown network {args.network!r}; known: {', '.join(networks)}")
    if net.get("mode") != "bot":
        sys.exit(f"{args.network}: only networks with mode: bot can send (see config/social.yaml)")

    ledger = load_ledger()
    if args.slug:
        posts = sorted(POSTS.glob(f"*-{args.slug}.md"))
        if not posts:
            sys.exit(f"no post file for slug {args.slug!r}")
        if not args.force and args.network in ledger.get(args.slug, {}):
            sys.exit(f"{args.slug} already posted to {args.network}: {ledger[args.slug][args.network]['url']}")
    else:
        args.posts, args.limit = [], 1
        posts = pick_posts(args, ledger, [args.network])
    if not posts:
        print("nothing to post")
        return

    path = posts[0]
    meta, _ = read_frontmatter(path)
    slug = slug_of(path)
    text = render(meta, net, slug)
    if args.dry_run:
        print(f"=== {slug} | {args.network} | dry run\n{text}")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("TELEGRAM_BOT_TOKEN is not set")
    message = tg_send(token, net["channel"], text)

    ledger.setdefault(slug, {})[args.network] = {
        "url": f"https://t.me/{net['channel'].lstrip('@')}/{message['message_id']}",
        "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    save_ledger(ledger)
    print(f"posted: {slug} → {args.network} {ledger[slug][args.network]['url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("plan", help="print what to post (for the /oil:social session)")
    pp.add_argument("posts", nargs="*", help="post files (default: every post of --date)")
    pp.add_argument("--to", help="comma-separated network keys (default: enabled in config)")
    pp.add_argument("--date", help="YYYY-MM-DD (default: latest post date)")
    pp.add_argument("--limit", type=int, help="max posts this run")
    pp.add_argument("--force", action="store_true", help="include posts already recorded in content/social.json")
    dp = sub.add_parser("done", help="record a successful post in content/social.json")
    dp.add_argument("slug")
    dp.add_argument("network")
    dp.add_argument("url")
    sp = sub.add_parser("send", help="send the next unposted article via Bot API (mode: bot networks)")
    sp.add_argument("network", nargs="?", default="telegram")
    sp.add_argument("--date", help="YYYY-MM-DD (default: latest post date)")
    sp.add_argument("--slug", help="post exactly this slug (ignores date picking)")
    sp.add_argument("--force", action="store_true", help="post even if already recorded in content/social.json")
    sp.add_argument("--dry-run", action="store_true", help="print the rendered post, don't send")
    sub.add_parser("status", help="show networks from config")
    args = ap.parse_args()

    networks = load_networks()
    if args.cmd == "plan":
        cmd_plan(args, networks)
    elif args.cmd == "done":
        cmd_done(args, networks)
    elif args.cmd == "send":
        cmd_send(args, networks)
    else:
        cmd_status(networks)


if __name__ == "__main__":
    main()
