# gtoil_content

Контент-фабрика статей о маслах. Статьи пишет плагин `oil` (папка `plugin/`, скилл `oil-writer`).

- `inbox/news/` — сырьё, собирает GitHub Actions (`collect-news.yml`). Руками не править.
- `drafts/YYYY-MM-DD/` — черновики, `status: draft`. Человек ставит `approved`.
- `python3 scripts/promote.py` — переносит approved в `docs/blog/posts/` (сайт на Pages).
- `content/index.json` — реестр всех статей, обновлять через `scripts/index_add.py`.
- Секреты — только `.env` / GitHub Secrets.
