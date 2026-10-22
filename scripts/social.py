#!/usr/bin/env python3
"""Post published articles to social networks through browser-use, logged in with saved cookies.

  social.py login vk            open a browser, log in by hand, save cookies to .browser/storage_state.json
  social.py post --to vk,x      post the latest articles; done pairs go to content/social.json
  social.py status              which networks have saved cookies
"""
import argparse
import asyncio
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from common import ROOT, read_frontmatter, slug_of

CONFIG = ROOT / "config" / "social.yaml"
POSTS = ROOT / "docs" / "blog" / "posts"
LEDGER = ROOT / "content" / "social.json"
STATE = ROOT / ".browser" / "storage_state.json"

load_dotenv(ROOT / ".env")
# browser-use phones home by default; the browser here carries live sessions, so opt out unless asked
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_CLOUD_SYNC", "false")


class PostResult(BaseModel):
    ok: bool
    post_url: str | None = None
    note: str = ""


def load_networks() -> dict[str, dict]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return {key: {**cfg.get("defaults", {}), **net} for key, net in cfg["networks"].items()}


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}


def save_ledger(ledger: dict) -> None:
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(title: str) -> str:
    """Same as mkdocs-material's default post_slugify (pymdownx.slugs.slugify(case="lower"))."""
    slug = re.sub(r"</?[^>]*>", "", unicodedata.normalize("NFC", title)).strip().lower()
    return re.sub(r"[^\w\- ]", "", slug).replace(" ", "-")


def post_url(meta: dict) -> str:
    """Site URL of a post, per `post_url_format: "{date}/{slug}"` in mkdocs.yml."""
    site = yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))["site_url"].rstrip("/")
    date = str(meta["date"])[:10].replace("-", "/")
    return f"{site}/blog/{date}/{meta.get('slug') or slugify(meta['title'])}/"


def hashtags(tags: list[str], limit: int) -> str:
    tags = (re.sub(r"\W", "", re.sub(r"[\s-]+", "_", t)) for t in tags[:limit])
    return " ".join(f"#{t}" for t in tags if t)


def render(meta: dict, net: dict) -> str:
    fields = {
        "title": meta["title"],
        "summary": " ".join(meta["summary"].split()),
        "url": post_url(meta),
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


def make_browser(*, headless: bool, domains: list[str] | None = None, keep_alive: bool = False):
    from browser_use import Browser

    # browser-use rewrites STATE (plus a .bak) on every cookie change, so lock the directory, not the file
    STATE.parent.mkdir(exist_ok=True)
    STATE.parent.chmod(0o700)
    # Fresh temp profile per run; the login lives in STATE, which browser-use loads on start
    # and writes back whenever cookies change and on close.
    return Browser(
        storage_state=str(STATE),
        user_data_dir=None,
        headless=headless,
        allowed_domains=domains,
        keep_alive=keep_alive,
    )


def make_llm():
    from browser_use import ChatAnthropic

    return ChatAnthropic(
        model=os.getenv("SOCIAL_MODEL", "claude-opus-5-5"),
        max_tokens=16000,
        # Besides thinking itself, this switches browser-use to tool_choice=auto;
        # forced tool choice is rejected by current Claude models.
        thinking={"type": "adaptive"},
        output_config={"effort": os.getenv("SOCIAL_EFFORT", "medium")},
        # Server-side retry on another model if a safety classifier declines a step.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )


def task_for(net: dict, text: str, dry_run: bool) -> str:
    final = (
        "НЕ нажимай кнопку публикации: оставь заполненную форму и сразу заверши задачу с ok=true."
        if dry_run
        else "Опубликуй пост. Убедись, что он появился, и верни его ссылку в post_url (не нашёл — null)."
    )
    return f"""Ты публикуешь пост в {net['name']} от имени уже залогиненного аккаунта.
Страница {net['compose_url']} уже открыта.

1. {net['instructions'].strip()}
2. Текст поста — всё между строками <<<POST и POST>>>. Введи его дословно, с теми же переносами строк, ничего не добавляя:
<<<POST
{text}
POST>>>
3. {final}

Если видишь форму входа, капчу, подтверждение по SMS/2FA или проверку «вы не робот» — ничего не вводи и не обходи,
заверши задачу с ok=false и опиши проблему в note. Не публикуй больше одного поста. Ничего не лайкай, не комментируй
и не меняй настроек аккаунта."""


async def publish(net: dict, text: str, *, llm, headless: bool, dry_run: bool) -> PostResult:
    from browser_use import Agent

    async def pause(_history) -> None:
        await asyncio.to_thread(input, "  Форма заполнена, пост НЕ опубликован. Проверь окно браузера и нажми Enter… ")

    agent = Agent(
        task=task_for(net, text, dry_run),
        llm=llm,
        browser=make_browser(headless=headless, domains=net.get("domains")),
        initial_actions=[{"navigate": {"url": net["compose_url"], "new_tab": False}}],
        output_model_schema=PostResult,
        use_thinking=False,  # adaptive thinking already covers it
        use_judge=False,
        register_done_callback=pause if dry_run else None,
    )
    history = await agent.run(max_steps=int(os.getenv("SOCIAL_MAX_STEPS", "40")))
    result = history.structured_output
    if result is None:
        return PostResult(ok=False, note=history.final_result() or "агент не закончил задачу")
    return result


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


async def cmd_post(args, networks: dict) -> None:
    targets = args.to.split(",") if args.to else [k for k, n in networks.items() if n.get("enabled")]
    unknown = [t for t in targets if t not in networks]
    if unknown:
        sys.exit(f"unknown networks: {', '.join(unknown)} (see config/social.yaml)")
    if not targets:
        sys.exit("no networks: pass --to vk,x or set enabled: true in config/social.yaml")
    if not STATE.exists():
        sys.exit("no saved login: run `python scripts/social.py login <network>` first")

    ledger = load_ledger()
    posts = pick_posts(args, ledger, targets)
    if not posts:
        print("nothing to post")
        return

    llm = make_llm()
    failed = 0
    for path in posts:
        meta, _ = read_frontmatter(path)
        slug = slug_of(path)
        for key in targets:
            if key in ledger.get(slug, {}) and not args.force:
                continue
            net = networks[key]
            text = render(meta, net)
            print(f"\n== {slug} → {net['name']}{' (dry run)' if args.dry_run else ''}\n{text}\n")
            result = await publish(net, text, llm=llm, headless=args.headless, dry_run=args.dry_run)
            print(f"  ok={result.ok} url={result.post_url} {result.note}".rstrip())
            if not result.ok:
                failed += 1
            elif not args.dry_run:
                ledger.setdefault(slug, {})[key] = {
                    "url": result.post_url,
                    "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                save_ledger(ledger)
    if failed:
        sys.exit(f"{failed} post(s) failed")


async def cmd_login(args, networks: dict) -> None:
    net = networks[args.network]
    browser = make_browser(headless=False, keep_alive=True)
    await browser.start()
    await browser.navigate_to(net["login_url"])
    await asyncio.to_thread(
        input, f"Войди в {net['name']} в открывшемся окне (капча и 2FA — руками), затем нажми здесь Enter… "
    )
    await browser.kill()  # writes cookies to STATE
    print(f"cookies saved to {STATE.relative_to(ROOT)}")


def cmd_status(networks: dict) -> None:
    cookies = json.loads(STATE.read_text(encoding="utf-8"))["cookies"] if STATE.exists() else []
    for key, net in networks.items():
        hosts = [d.removeprefix("*.") for d in net.get("domains") or [urlparse(net["login_url"]).hostname]]
        n = sum(1 for c in cookies for h in hosts if c["domain"].lstrip(".") == h or c["domain"].endswith("." + h))
        print(f"{key:10} {'enabled ' if net.get('enabled') else 'disabled'}  cookies: {n}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("login", help="log in by hand and save cookies")
    lp.add_argument("network")
    pp = sub.add_parser("post", help="post articles from docs/blog/posts")
    pp.add_argument("posts", nargs="*", help="post files (default: every post of --date)")
    pp.add_argument("--to", help="comma-separated network keys (default: enabled in config)")
    pp.add_argument("--date", help="YYYY-MM-DD (default: latest post date)")
    pp.add_argument("--limit", type=int, help="max posts this run")
    pp.add_argument("--dry-run", action="store_true", help="fill the form, don't publish")
    pp.add_argument("--headless", action="store_true", help="hide the browser window")
    pp.add_argument("--force", action="store_true", help="post again even if content/social.json has it")
    sub.add_parser("status", help="show networks and saved cookies")
    args = ap.parse_args()

    networks = load_networks()
    if args.cmd == "login":
        if args.network not in networks:
            sys.exit(f"unknown network {args.network!r}; known: {', '.join(networks)}")
        asyncio.run(cmd_login(args, networks))
    elif args.cmd == "post":
        asyncio.run(cmd_post(args, networks))
    else:
        cmd_status(networks)


if __name__ == "__main__":
    main()
