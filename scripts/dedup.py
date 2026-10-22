#!/usr/bin/env python3
"""Exit 1 if a proposed title is too similar to an existing article in content/index.json."""
import argparse
import sys
from difflib import SequenceMatcher

from common import load_index


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--threshold", type=float, default=0.75)
    args = ap.parse_args()

    title = args.title.lower()
    hits = [
        (r, i) for i in load_index()
        if (r := SequenceMatcher(None, title, i["title"].lower()).ratio()) >= args.threshold
    ]
    for r, i in sorted(hits, key=lambda h: -h[0]):
        print(f"{r:.2f}  {i['date']}  {i['title']}  ({i['path']})")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
