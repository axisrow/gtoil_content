"""Smoke-тест механики scripts/social.py (плагин /oil:social). Запуск: python3 tests/test_social.py"""
import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import yaml

import social
from common import slug_of
from social import cmd_done, cmd_plan, hashtags, load_ledger, load_networks, pick_posts, post_url, render

checks = []


def check(name, cond, detail=""):
    checks.append((name, cond, detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")


def ns(**kw):
    base = dict(posts=[], to=None, date=None, force=False, limit=None)
    base.update(kw)
    return argparse.Namespace(**base)


nets = load_networks()
check("config: 8 сетей", set(nets) == {"vk", "telegram", "x", "threads", "linkedin", "facebook", "ok", "dzen"}, str(sorted(nets)))
check("config: defaults смержены", all("template" in n and "hashtags" in n for n in nets.values()))
check("config: все сети disabled", not any(n.get("enabled") for n in nets.values()))
check("config: у всех есть compose_url и domains", all(n.get("compose_url") and n.get("domains") for n in nets.values()))

# реальный опубликованный пост: слаг живёт в имени файла, в front-matter его нет
posts = sorted(social.POSTS.glob("*.md"))
check("посты найдены", bool(posts), str(len(posts)))
latest = max(p.name[:10] for p in posts)
path = next(p for p in posts if p.name.startswith(latest))
meta, _ = social.read_frontmatter(path)
check("front-matter читается", bool(meta.get("title")) and bool(meta.get("summary")))

fs = slug_of(path)
site = yaml.safe_load((social.ROOT / "mkdocs.yml").read_text(encoding="utf-8"))["site_url"].rstrip("/")
url = post_url(meta, fs)
check("post_url формат", url == f"{site}/blog/{latest.replace('-', '/')}/{fs}/", url)

# хэштеги
check("hashtags: пробел/дефис → _", hashtags(["моторные масла", "GTL-база"], 5) == "#моторные_масла #GTL_база", hashtags(["моторные масла", "GTL-база"], 5))
check("hashtags: пустые отфильтрованы, лимит", hashtags(["a b", "!!!", "c"], 1) == "#a_b", hashtags(["a b", "!!!", "c"], 1))

# рендер по каждой сети на реальном посте
for key, net in nets.items():
    t = render(meta, net, fs)
    limit = net.get("max_len")
    ok = t.count(url) == 1 and meta["title"] in t
    if limit:
        ok = ok and len(t) <= limit
    check(f"render[{key}]: шаблон+лимит", ok, f"len={len(t)} max={limit}")

# обрезка на детерминированных данных: title 30, url 77, summary 100, hashtags 7 → full 220
m = {"title": "T" * 30, "summary": "S" * 100, "date": latest, "tags": ["a b", "c"], "slug": fs}
vk = {**nets["vk"], "template": "{title}\n\n{summary}\n\n{url}\n\n{hashtags}", "hashtags": 5}
t1 = render(m, {**vk, "max_len": 200}, fs)
check("обрезка: summary ужат с …", t1.count("…") == 1 and "T" * 30 in t1 and len(t1) <= 200, f"len={len(t1)}")
t2 = render(m, {**vk, "max_len": 115}, fs)
check("обрезка: hashtags выброшены, title+url целы", "#" not in t2 and "T" * 30 in t2 and url in t2 and len(t2) <= 115, f"len={len(t2)}")
try:
    render(m, {**vk, "max_len": 50}, fs)
    check("обрезка: ValueError на невозможном", False)
except ValueError:
    check("обрезка: ValueError на невозможном", True)

# X: url считается за 23 символа (url_len), а не за свои 77
check("render[x]: url_len=23 учтён", render(m, {**nets["x"], "max_len": 55}, fs) == "T" * 30 + f"\n\n{url}")
try:
    render(m, {**nets["x"], "max_len": 54}, fs)
    check("render[x]: лимит с url_len работает", False)
except ValueError:
    check("render[x]: лимит с url_len работает", True)

# pick_posts
ledger = load_ledger()
check("ledger пустой dict", isinstance(ledger, dict) and not ledger, str(ledger)[:80])
picked = pick_posts(ns(date=latest), ledger, ["x"])
check("pick_posts: посты последней даты", all(p.name.startswith(latest) for p in picked), f"{len(picked)} шт")
check("pick_posts: limit", len(pick_posts(ns(date=latest, limit=2), ledger, ["x"])) <= 2)
check("pick_posts: явные файлы", pick_posts(ns(posts=[str(path)]), ledger, ["x"]) == [path.resolve()])
fake = {fs: {"x": {}}}
check("pick_posts: опубликованное скипается", path not in pick_posts(ns(date=latest), fake, ["x"]))
check("pick_posts: force возвращает", path in pick_posts(ns(date=latest, force=True), fake, ["x"]))

# cmd_plan: блоки для сессии-агента
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    cmd_plan(ns(to="vk", date=latest, limit=1), nets)
out = buf.getvalue()
check("plan: заголовок блока", f"=== {fs} | vk | ВКонтакте" in out)
check("plan: compose и domains", f"compose: {nets['vk']['compose_url']}" in out and "*.vk.com, *.vk.ru" in out)
check("plan: instructions из конфига", "instructions: " in out and "Опубликовать" in out or "Кликни" in out)
check("plan: текст между POST-маркерами", "<<<POST\n" in out and "\nPOST>>>" in out and url in out)
check("plan: одна пара = один блок", out.count("<<<POST") == 1, str(out.count("<<<POST")))

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    cmd_plan(ns(to="vk,x", date=latest, limit=1), nets)
check("plan: две сети — два блока", buf.getvalue().count("<<<POST") == 2)

# занесённое в ledger пропускается
with tempfile.TemporaryDirectory() as td:
    social.LEDGER = Path(td) / "social.json"
    latest_all = {slug_of(p): {"x": {}} for p in posts if p.name.startswith(latest)}
    social.LEDGER.write_text(json.dumps(latest_all), encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_plan(ns(to="x", date=latest), nets)
    check("plan: опубликованное скипается", "<<<POST" not in buf.getvalue())
try:
    cmd_plan(ns(to="nope"), nets)
    check("plan: unknown network → exit", False)
except SystemExit:
    check("plan: unknown network → exit", True)

# cmd_done: пишет ledger во временный файл
with tempfile.TemporaryDirectory() as td:
    social.LEDGER = Path(td) / "social.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_done(argparse.Namespace(slug=fs, network="vk", url="https://vk.com/wall_1"), nets)
    saved = json.loads(social.LEDGER.read_text(encoding="utf-8"))
    check("done: запись с url и временем", saved[fs]["vk"]["url"] == "https://vk.com/wall_1" and "posted_at" in saved[fs]["vk"])
    with contextlib.redirect_stdout(io.StringIO()):
        cmd_done(argparse.Namespace(slug=fs, network="x", url="https://x.com/1"), nets)
    saved = json.loads(social.LEDGER.read_text(encoding="utf-8"))
    check("done: вторая сеть той же статьи", set(saved[fs]) == {"vk", "x"})
    try:
        cmd_done(argparse.Namespace(slug=fs, network="nope", url="u"), nets)
        check("done: unknown network → exit", False)
    except SystemExit:
        check("done: unknown network → exit", True)

failed = [c for c in checks if not c[1]]
print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
