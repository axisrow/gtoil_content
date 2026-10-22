# gtoil_content

Ежедневно ~5 статей о моторных и индустриальных маслах: новости индустрии, матчасть, советы экспертов, мифы.

```
GitHub Actions (каждые 6ч) ──RSS──▶ inbox/news/*.json
Claude Code: /oil:daily ──────────▶ drafts/<дата>/*.md     ← ты проверяешь, ставишь status: approved
scripts/promote.py ───────────────▶ docs/blog/posts/       ← push в main
GitHub Pages ◀────────────────────  витрина + RSS-фид (задел под автопостинг)
```

## Установка (один раз)

```bash
git clone https://github.com/axisrow/gtoil_content && cd gtoil_content
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

В Claude Code (из папки репо):
```
/plugin marketplace add ./
/plugin install oil@gtoil
```

На GitHub: **Settings → Pages → Source: GitHub Actions**, **Settings → Actions → General → Workflow permissions: Read and write**.

## Каждый день

```bash
git pull                       # свежие новости от Actions
claude "/oil:daily"            # 5 черновиков в drafts/<сегодня>/
# читаешь, правишь, в нужных статьях status: draft → approved
python3 scripts/promote.py     # approved → docs/blog/posts/
mkdocs serve                   # (опц.) превью на http://127.0.0.1:8000
git add -A && git commit -m "posts: $(date +%F)" && git push
```

Другие команды: `/oil:article <тема> [news|deep|expert|myth]`, `/oil:review drafts/…/file.md`.

## Настройка
- `config/sources.yaml` — RSS-ленты и ключевые слова.
- `config/topics_backlog.md` — банк вечнозелёных тем.
- `plugin/skills/oil-writer/style.md`, `rubrics.md` — голос и сетка рубрик.

## Дальше
- Автопостинг: RSS сайта (`feed_rss_created.xml`) → TG/VK/Дзен, либо свой скрипт с токенами из `.env`.
- Автогенерация: облачная scheduled task Claude Code, запускающая `/oil:daily` утром и открывающая PR.
