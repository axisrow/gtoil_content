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

## Автопостинг в соцсети (/oil:social)

Публикация идёт в сессии Claude Code: механику (тексты, лимиты, журнал) даёт `scripts/social.py`, браузером управляет сама сессия через проектную команду `/browser-use` — скилл browser-use, CDP-демон и твой обычный Chrome, где сессии соцсетей уже живут. Запускается локально, на Mac: соцсети не любят IP дата-центров.

```bash
/oil:social vk --dry-run     # агент заполнит форму, но не нажмёт «Опубликовать»
/oil:social vk,telegram      # статьи за последнюю дату
```

Механика доступна и из терминала (нужен только PyYAML из `requirements.txt`):

```bash
python3 scripts/social.py plan --to vk   # что пойдёт в сети: тексты, compose_url, инструкции
python3 scripts/social.py status         # сети из config/social.yaml
```

- **Сети** настраиваются в `config/social.yaml`: страница публикации (`compose_url` — своя группа или канал), инструкция агенту, лимит длины, шаблон поста, разрешённые домены. Новая сеть — новый блок в этом файле, код трогать не нужно. `enabled: true` — публикация без явного списка сетей.
- **Журнал** `content/social.json`: что, куда и когда опубликовано; запись делает `social.py done` (его вызывает сессия после успешного поста). Повторно та же статья в ту же сеть не уйдёт (`--force` отменяет). Журнал коммить.
- Капча, 2FA или форма входа во время публикации — агент останавливается и ничего не вводит.
- Автоматизация браузера нарушает правила части площадок (X, LinkedIn, Meta), и аккаунт могут ограничить. Где есть официальный API (Telegram Bot API, VK API), надёжнее постить через него.

## Дальше
- Автогенерация: облачная scheduled task Claude Code, запускающая `/oil:daily` утром и открывающая PR.
