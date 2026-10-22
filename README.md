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

## Автопостинг в соцсети (browser-use)

Агент [browser-use](https://github.com/browser-use/browser-use) на Claude открывает браузер под твоим аккаунтом и публикует анонсы статей с сайта. Запускается локально, на Mac: соцсети не любят входы с IP дата-центров, а куки — тот же пароль.

```bash
uv venv -p 3.12 && source .venv/bin/activate     # нужен Python 3.11+
uv pip install -r requirements-social.txt
cp .env.example .env                              # впиши ANTHROPIC_API_KEY

python scripts/social.py login vk                 # откроется окно: войди руками (2FA, капча), Enter в терминале
python scripts/social.py status                   # у каких сетей есть куки
python scripts/social.py post --to vk --dry-run   # агент заполнит форму, но не нажмёт «Опубликовать»
python scripts/social.py post --to vk,telegram    # статьи за последнюю дату
```

- **Куки** лежат в `.browser/storage_state.json` (каталог в `.gitignore`, права 700). Каждый запуск поднимает чистый профиль Chromium, подгружает их, а обновлённые сессии пишет обратно. Разлогинило — повтори `login`. Браузер берётся из Playwright Chromium или установленного Google Chrome; если нет ни того, ни другого, browser-use поставит Chromium сам.
- **Сети** настраиваются в `config/social.yaml`: страница публикации (`compose_url` — своя группа или канал), инструкция агенту, лимит длины, шаблон поста, разрешённые домены. Новая сеть — новый блок в этом файле, код трогать не нужно. `enabled: true` — публиковать без `--to`.
- **Журнал** `content/social.json`: что, куда и когда опубликовано. Повторно та же статья в ту же сеть не уйдёт (кроме `--force`). Журнал коммить.
- Другие флаги: `post <файлы.md>`, `--date YYYY-MM-DD`, `--limit N`, `--headless`. Модель и глубину рассуждений задают `SOCIAL_MODEL` / `SOCIAL_EFFORT` в `.env`.
- Капча, 2FA или форма входа во время публикации — агент останавливается и ничего не вводит. Телеметрию browser-use скрипт отключает.
- Автоматизация браузера нарушает правила части площадок (X, LinkedIn, Meta), и аккаунт могут ограничить. Где есть официальный API (Telegram Bot API, VK API), надёжнее постить через него.

## Дальше
- Автогенерация: облачная scheduled task Claude Code, запускающая `/oil:daily` утром и открывающая PR.
