"""Index persistence and query execution."""

from __future__ import annotations

import json
from pathlib import Path

from indexer import Indexer


def save_index(idx: Indexer, path: Path) -> None:
    """Write the index to a JSON file (creating parent dirs as needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(idx.to_dict(), handle, indent=2, ensure_ascii=False)


def load_index(path: Path) -> Indexer:
    """Load an index from a JSON file produced by ``save_index``."""
    if not path.exists():
        raise FileNotFoundError(
            f"no index at {path} — run `build` first to create one"
        )
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Indexer.from_dict(data)


def print_postings(idx: Indexer, word: str) -> str:
    """Return a human-readable postings listing for ``word``."""
    term = word.lower()
    postings = idx.index.get(term)
    if not postings:
        return f"'{word}' is not in the index."

    lines = [f"{term}: {len(postings)} document(s)"]
    for url in sorted(postings):
        entry = postings[url]
        lines.append(
            f"  {url}  freq={entry['freq']}  positions={entry['positions']}"
        )
    return "\n".join(lines)


def find_pages(idx: Indexer, terms: list[str]) -> list[str]:
    """Return URLs that contain every term (conjunctive AND query)."""
    cleaned = [t.lower() for t in terms if t.strip()]
    if not cleaned:
        return []

    url_sets: list[set[str]] = []
    for term in cleaned:
        postings = idx.index.get(term)
        if not postings:
            return []
        url_sets.append(set(postings.keys()))

    result = set.intersection(*url_sets)
    return sorted(result)
