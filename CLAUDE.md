# gtoil_content

Контент-фабрика статей о маслах. Статьи пишет плагин `oil` (папка `plugin/`, скилл `oil-writer`).

- `inbox/news/` — сырьё, собирает GitHub Actions (`collect-news.yml`). Руками не править.
- `drafts/YYYY-MM-DD/` — черновики, приходят PR-ом от scheduled task. Merge PR = одобрение.
- `promote.yml` (`scripts/promote.py --all`) переносит смерженные черновики в `docs/blog/posts/` и деплоит Pages.
- `content/index.json` — реестр всех статей, обновлять через `scripts/index_add.py`.
- `scripts/social.py` публикует статьи в соцсети через локальный Claude Code + CDP-демон browser-use (обычный Chrome пользователя, без API-ключей); сети — `config/social.yaml`, журнал — `content/social.json`. Запускается только локально, в облачной сессии браузера нет.
- Секреты — только `.env` / GitHub Secrets.
