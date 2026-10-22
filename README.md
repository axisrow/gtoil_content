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

## Дальше
- Автопостинг: RSS сайта (`feed_rss_created.xml`) → TG/VK/Дзен, либо свой скрипт с токенами из `.env`.
- Автогенерация: облачная scheduled task Claude Code, запускающая `/oil:daily` утром и открывающая PR.
