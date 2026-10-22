#!/usr/bin/env python3
"""Move drafts marked `status: approved` (or all drafts with --all) into docs/blog/posts and update the index."""
import argparse

from common import ROOT, read_frontmatter, slug_of, write_frontmatter
from index_add import main as index_add

POSTS = ROOT / "docs" / "blog" / "posts"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="approve every draft (merged PR = approval)")
    args = ap.parse_args()
    moved = []
    for draft in sorted((ROOT / "drafts").glob("*/*.md")):
        meta, body = read_frontmatter(draft)
        if args.all:
            meta["status"] = "approved"
        elif meta.get("status") != "approved":
            continue
        slug = slug_of(draft)
        target = POSTS / f"{meta['date']}-{slug}.md"
        POSTS.mkdir(parents=True, exist_ok=True)
        write_frontmatter(target, meta, body)
        draft.unlink()
        moved.append(str(target))
        print(f"{draft.relative_to(ROOT)} -> {target.relative_to(ROOT)}")
    if moved:
        index_add(moved)
    else:
        print("no approved drafts")


if __name__ == "__main__":
    main()
