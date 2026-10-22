# gtoil_content

Контент-фабрика статей о маслах. Статьи пишет плагин `oil` (папка `plugin/`, скилл `oil-writer`).

- `inbox/news/` — сырьё, собирает GitHub Actions (`collect-news.yml`). Руками не править.
- `config/competitors.yaml` — конкуренты GT OIL с сайтами; `inbox/competitors/` — свежие статьи из их разделов (Actions). Только идеи тем: конкурентов в статьях не называем.
- `drafts/YYYY-MM-DD/` — черновики, приходят PR-ом от scheduled task. Merge PR = одобрение.
- `promote.yml` (`scripts/promote.py --all`) переносит смерженные черновики в `docs/blog/posts/` и деплоит Pages.
- `content/index.json` — реестр всех статей, обновлять через `scripts/index_add.py`.
- Секреты — только `.env` / GitHub Secrets.
