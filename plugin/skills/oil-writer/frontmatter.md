# Front-matter

```yaml
---
title: "Заголовок статьи"
date: 2026-10-22            # дата выпуска, YYYY-MM-DD
rubric: news                # news | deep | expert | myth
categories:                 # для сайта (MkDocs blog); одно значение по рубрике:
  - Новости                 # news→Новости, deep→Матчасть, expert→Советы, myth→Мифы
tags: [моторное масло, ACEA]
summary: "Анонс до 280 знаков для соцсетей."
sources:
  - https://example.com/article
inspired_by:                # необязательно: статьи конкурентов, давшие идею (на сайте не выводятся)
  - https://competitor.example/article
status: draft               # draft → approved (человек) → published
---
```

После front-matter: тело Markdown. Первый абзац — лид, затем строка `<!-- more -->` (отсечка анонса на сайте), затем основной текст. `# Заголовок` в теле не дублировать.
