# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# gtoil_content

Контент-фабрика: ~5 статей о маслах в день. Статьи пишет плагин `oil` (папка `plugin/`, скилл `oil-writer`), сайт — MkDocs Material на GitHub Pages (`mkdocs.yml`, `docs/`).

## Конвейер

1. **Сбор сырья** — Actions `collect-news.yml` каждые 6 ч: `scripts/fetch_rss.py` (RSS-ленты из `config/sources.yaml`) → `inbox/news/`, `scripts/fetch_competitors.py` (разделы статей из `config/competitors.yaml`, пробует rss → html → sitemap) → `inbox/competitors/`. Push в main, затрагивающий коллекторы или их конфиги, перезапускает сбор.
2. **Написание** — `/oil:daily` (5 статей по слотам из `rubrics.md`), `/oil:article <тема> [rubric]`, `/oil:review <файл>`. Черновики: `drafts/YYYY-MM-DD/NN-slug.md` (NN = 01..05); вечнозелёные темы — из `config/topics_backlog.md` (после использования отметить `[x]`).
3. **Одобрение** — черновики приезжают PR-ом «Статьи YYYY-MM-DD» от scheduled task; merge PR = одобрение всех оставшихся в нём статей (неудачные человек удаляет до мержа).
4. **Публикация** — push в main с изменениями в `drafts/**` запускает `promote.yml`: `scripts/promote.py --all` переносит черновики в `docs/blog/posts/YYYY-MM-DD-slug.md`, обновляет индекс, коммитит и явно вызывает `pages.yml` (коммит с GITHUB_TOKEN сам `pages.yml` не триггерит).

## Команды

Зависимости: `pip install -r requirements.txt` (для коллекторов достаточно `feedparser` + `PyYAML`). Тестов и линтеров в репо нет.

```bash
python3 scripts/fetch_rss.py --hours 48           # новости → inbox/news/<сегодня>.json
python3 scripts/fetch_competitors.py              # конкуренты → inbox/competitors/<сегодня>.json
python3 scripts/dedup.py "<заголовок>"            # exit 1 = уже есть похожая статья
python3 scripts/index_add.py drafts/<дата>/*.md   # добавить/обновить записи в content/index.json
python3 scripts/promote.py --all                  # drafts → docs/blog/posts + индекс (локально;
                                                  # без --all — только черновики со status: approved)
mkdocs build --strict                             # сборка сайта, как в CI Pages
mkdocs serve                                      # локальный просмотр
```

## Контракты данных

- **Front-matter** (схема: `plugin/skills/oil-writer/frontmatter.md`) — обязательны `title`, `date`, `rubric` (news|deep|expert|myth), `summary` (≤280 знаков), `status` (draft → approved); `index_add.py` падает без них. Рубрика маппится в `categories`: news→Новости, deep→Матчасть, expert→Советы, myth→Мифы (другие запрещены в `mkdocs.yml`).
- **Тело**: лид, затем `<!-- more -->` (blog-плагин требует отсечку анонса), основной текст без дубля `# Заголовок`. Непроверенные места — `<!-- CHECK: ... -->`.
- **Слаг**: префикс `NN-` у черновиков / `YYYY-MM-DD-` у постов срезает `slug_of()` (`scripts/common.py`) — слаг должен сохраниться при переносе, по нему ключуется `content/index.json`. `promote.py` проставляет посту `slug` из имени файла — URL на Pages латиницей (`blog/<дата>/<слаг>/`).
- `content/index.json` — единственный реестр статей (дедуп, баланс рубрик); править только через `index_add.py`.

## Правила контента

- `inbox/` — сырьё от Actions, руками не править (их коммиты затрут правки).
- Конкурентов из `config/competitors.yaml` в статьях не называть и не сравнивать; их разделы — только источник тем (ссылка на статью-идею — в `inspired_by`, не в `sources`).
- Новостям — ≥1 URL в `sources`; все цифры и даты из первоисточника.
- Факты — по `plugin/skills/oil-writer/style.md`: не выдумывать допуски, спецификации, вязкости, цены, цитаты.
- Секреты — только `.env` (в `.gitignore`) / GitHub Secrets.
