"""Index persistence and query execution."""

from __future__ import annotations

import json
import math
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


def _idf(idx: Indexer, term: str) -> float:
    """Inverse document frequency for ``term`` (classic, base e).

    Only called after ``find_pages`` has verified the term has postings,
    so ``df >= 1`` is guaranteed.
    """
    df = len(idx.index[term])
    return math.log(idx.num_documents / df)


def _score(idx: Indexer, terms: list[str], url: str) -> float:
    """Length-normalized TF-IDF score of ``url`` against ``terms``.

    Only called on AND-matched URLs, which therefore have ``length >= 1``.
    """
    length = idx.docs[url]["length"]
    total = 0.0
    for term in terms:
        freq = idx.index[term][url]["freq"]
        total += (freq / length) * _idf(idx, term)
    return total


def find_pages(idx: Indexer, terms: list[str]) -> list[tuple[str, float]]:
    """Return ``(url, score)`` pairs for pages matching every term, ranked by
    descending TF-IDF score (ties broken alphabetically by URL)."""
    cleaned = list(dict.fromkeys(t.lower() for t in terms if t.strip()))
    if not cleaned:
        return []

    url_sets: list[set[str]] = []
    for term in cleaned:
        postings = idx.index.get(term)
        if not postings:
            return []
        url_sets.append(set(postings.keys()))

    matched = set.intersection(*url_sets)
    scored = [(url, _score(idx, cleaned, url)) for url in matched]
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return scored
