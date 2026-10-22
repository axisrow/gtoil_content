#!/usr/bin/env python3
"""Add or refresh articles in content/index.json from their front-matter."""
import sys
from pathlib import Path

from common import ROOT, load_index, read_frontmatter, save_index, slug_of

REQUIRED = ("title", "date", "rubric", "summary", "status")


def main(paths: list[str]) -> None:
    index = {i["slug"]: i for i in load_index()}
    for p in map(Path, paths):
        meta, _ = read_frontmatter(p)
        missing = [k for k in REQUIRED if not meta.get(k)]
        if missing:
            sys.exit(f"{p}: missing {', '.join(missing)}")
        slug = slug_of(p)
        index[slug] = {
            "slug": slug,
            "title": meta["title"],
            "date": str(meta["date"]),
            "rubric": meta["rubric"],
            "tags": meta.get("tags", []),
            "status": meta["status"],
            "path": str(p.resolve().relative_to(ROOT)),
        }
        print(f"indexed {slug}")
    save_index(sorted(index.values(), key=lambda i: (i["date"], i["path"])))


if __name__ == "__main__":
    main(sys.argv[1:])
