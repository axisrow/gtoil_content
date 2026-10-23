#!/usr/bin/env python3
"""Post published articles to social networks: Claude Code drives the user's own Chrome.

  social.py status              show networks from config/social.yaml
  social.py post --to vk,x      post the latest articles; done pairs go to content/social.json

The brain is a headless `claude -p` run (subscription auth, no API key), the hands are the
browser-use skill: a CDP daemon attached to the user's regular Chrome, where social logins
already live. There is nothing to log in here.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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


def run_agent(task: str) -> str:
    """Headless Claude Code with only the browser-use skill's Bash commands allowed."""
    cmd = [
        "claude", "-p", task,
        "--allowedTools", "Bash(browser-use:*)",
        "--max-turns", os.getenv("SOCIAL_MAX_TURNS", "40"),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                              timeout=int(os.getenv("SOCIAL_TIMEOUT", "900")))
    except subprocess.TimeoutExpired:
        return "RESULT: fail не уложился в SOCIAL_TIMEOUT"
    if proc.returncode != 0:
        tail = (proc.stderr.strip().splitlines() or ["без вывода"])[-1]
        return f"RESULT: fail claude завершился с ошибкой: {tail}"
    return proc.stdout


def agent_result(out: str) -> str:
    """The `RESULT: ...` line the task demands as its last line; '' if the agent forgot it."""
    found = re.findall(r"^\s*RESULT:\s*(.+)$", out, re.MULTILINE)
    return found[-1].strip() if found else ""


def task_for(net: dict, text: str, dry_run: bool) -> str:
    if dry_run:
        final = "НЕ нажимай кнопку публикации: оставь заполненную форму и сразу заверши задачу."
        ok_note = "форма заполнена, пост НЕ опубликован"
    else:
        final = "Опубликуй пост кнопкой публикации, убедись, что он появился, и достань ссылку на него."
        ok_note = "пост опубликован: <ссылка на него>"
    return f"""Ты публикуешь пост в {net['name']}. Управляй браузером пользователя через CDP-демон browser-use
(скилл browser-use): Chrome уже открыт и залогинен, отдельно входить не нужно.

1. Открой страницу публикации новой вкладкой: new_tab("{net['compose_url']}"), дальше работай в ней.
2. {net['instructions'].strip()}
3. Текст поста — всё между строками <<<POST и POST>>>. Введи его дословно, с теми же переносами строк,
   ничего не добавляя и не исправляя:
<<<POST
{text}
POST>>>
4. {final}

Не отходи от доменов {', '.join(net.get('domains') or [net['compose_url']])}: чужие страницы не открывай.
Если видишь форму входа, капчу, 2FA или «вы не робот» — ничего не вводи и не обходи, заверши задачу.
Не публикуй больше одного поста. Ничего не лайкай, не комментируй и не меняй настроек аккаунта.
Последней строкой ответа выведи ровно одну строку: RESULT: ok ({ok_note}) или RESULT: fail <что случилось>."""


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


def cmd_post(args, networks: dict) -> None:
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

    failed = 0
    for path in posts:
        meta, _ = read_frontmatter(path)
        slug = slug_of(path)
        for key in targets:
            if key in ledger.get(slug, {}) and not args.force:
                continue
            net = networks[key]
            text = render(meta, net, slug)
            print(f"\n== {slug} → {net['name']}{' (dry run)' if args.dry_run else ''}\n{text}\n")
            out = run_agent(task_for(net, text, args.dry_run))
            print("\n".join(f"  {line}" for line in out.strip().splitlines()))
            answer = agent_result(out)
            url = re.search(r"https?://\S+", answer.removeprefix("ok"))
            if not answer.startswith("ok"):
                failed += 1
            elif url and not args.dry_run:
                ledger.setdefault(slug, {})[key] = {
                    "url": url.group(0).rstrip(").,"),
                    "posted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                save_ledger(ledger)
    if failed:
        sys.exit(f"{failed} post(s) failed")


def cmd_status(networks: dict) -> None:
    for key, net in networks.items():
        print(f"{key:10} {'enabled ' if net.get('enabled') else 'disabled'}  {net['compose_url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("post", help="post articles from docs/blog/posts")
    pp.add_argument("posts", nargs="*", help="post files (default: every post of --date)")
    pp.add_argument("--to", help="comma-separated network keys (default: enabled in config)")
    pp.add_argument("--date", help="YYYY-MM-DD (default: latest post date)")
    pp.add_argument("--limit", type=int, help="max posts this run")
    pp.add_argument("--dry-run", action="store_true", help="fill the form, don't publish")
    pp.add_argument("--force", action="store_true", help="post again even if content/social.json has it")
    sub.add_parser("status", help="show networks from config")
    args = ap.parse_args()

    networks = load_networks()
    if args.cmd == "post":
        cmd_post(args, networks)
    else:
        cmd_status(networks)


if __name__ == "__main__":
    main()
