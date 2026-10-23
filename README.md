# gtoil_content

Ежедневно ~5 статей о моторных и индустриальных маслах: новости индустрии, матчасть, советы экспертов, мифы.

```
GitHub Actions (каждые 6ч) ──RSS──▶ inbox/news/*.json
Claude Code: /oil:daily ──────────▶ drafts/<дата>/*.md     ← ты проверяешь, ставишь status: approved
scripts/promote.py ───────────────▶ docs/blog/posts/       ← push в main
GitHub Pages ◀────────────────────  витрина + RSS-фид (задел под автопостинг)
```

## Облачный флоу (ничего локально)

1. **Actions `Collect news`** каждые 6 ч кладут новости в `inbox/news/`.
2. **Scheduled task Claude Code** каждое утро открывает облачную сессию, плагин `oil` (подключается автоматически через `.claude/settings.json`) пишет 5 статей и открывает PR «Статьи <дата>».
3. **Ты в PR** (браузер/телефон): читаешь, правишь файлы прямо на GitHub, удаляешь неудачные статьи, жмёшь Merge.
4. **Actions `Promote`** переносит смерженные черновики в `docs/blog/posts/` и деплоит **Pages**.

Один раз на GitHub: **Settings → Pages → Source: GitHub Actions**; **Settings → Actions → General → Workflow permissions: Read and write**.

Команды плагина (в любой облачной сессии на этом репо): `/oil:daily`, `/oil:article <тема> [news|deep|expert|myth]`, `/oil:review <файл>`.

## Настройка
- `config/sources.yaml` — RSS-ленты и ключевые слова.
- `config/topics_backlog.md` — банк вечнозелёных тем.
- `plugin/skills/oil-writer/style.md`, `rubrics.md` — голос и сетка рубрик.

## Автопостинг в соцсети (Claude Code + browser-use)

Мозг — локальный Claude Code в headless-режиме (`claude -p`, работает под подпиской, ключ API не нужен), руки — скилл [browser-use](https://github.com/browser-use/browser-use): CDP-демон управляет твоим обычным Chrome, где сессии соцсетей уже живут. Запускается локально, на Mac: соцсети не любят входы с IP дата-центров.

```bash
python3 scripts/social.py status                   # сети из config/social.yaml
python3 scripts/social.py post --to vk --dry-run   # агент заполнит форму, но не нажмёт «Опубликовать»
python3 scripts/social.py post --to vk,telegram    # статьи за последнюю дату
```

Зависимости: `claude` CLI (вход в Claude Code уже настроен) и `browser-use` CLI (ставится по его скиллу); из Python — только PyYAML, он уже в `requirements.txt`.

- **Вход** отдельный не нужен: агент работает в твоём Chrome. Разлогинило — войди руками в браузер, скрипту сказать нечего.
- **Сети** настраиваются в `config/social.yaml`: страница публикации (`compose_url` — своя группа или канал), инструкция агенту, лимит длины, шаблон поста, разрешённые домены. Новая сеть — новый блок в этом файле, код трогать не нужно. `enabled: true` — публиковать без `--to`.
- **Журнал** `content/social.json`: что, куда и когда опубликовано. Повторно та же статья в ту же сеть не уйдёт (кроме `--force`). Журнал коммить.
- Другие флаги: `post <файлы.md>`, `--date YYYY-MM-DD`, `--limit N`. Лимиты агента — `SOCIAL_MAX_TURNS` (ходов) и `SOCIAL_TIMEOUT` (секунд) в окружении.
- Капча, 2FA или форма входа во время публикации — агент останавливается и ничего не вводит. Ему разрешены только команды `browser-use`, выйти на чужие домены инструкция запрещает.
- Автоматизация браузера нарушает правила части площадок (X, LinkedIn, Meta), и аккаунт могут ограничить. Где есть официальный API (Telegram Bot API, VK API), надёжнее постить через него.

## Дальше
- Автогенерация: облачная scheduled task Claude Code, запускающая `/oil:daily` утром и открывающая PR.
