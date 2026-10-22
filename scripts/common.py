"""Shared helpers: repo paths, front-matter parsing, article index."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "content" / "index.json"


def read_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: no front-matter")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body


def write_frontmatter(path: Path, meta: dict, body: str) -> None:
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm}---{body}", encoding="utf-8")


def slug_of(path: Path) -> str:
    """Strip the `NN-` (drafts) or `YYYY-MM-DD-` (posts) prefix from a file stem."""
    return re.sub(r"^(\d{4}-\d{2}-\d{2}|\d{2})-", "", path.stem)


def load_index() -> list[dict]:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []


def save_index(items: list[dict]) -> None:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
