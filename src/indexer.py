"""Tokenisation and inverted-index construction."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lower-case the text and return a list of alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


def extract_text(html: str) -> tuple[str, str]:
    """Return (title, visible_text) from an HTML document."""
    soup = BeautifulSoup(html, "lxml")
    for element in soup(["script", "style"]):
        element.decompose()
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    body = soup.body if soup.body else soup
    text = body.get_text(" ", strip=True)
    return title, text


class Indexer:
    """In-memory inverted index plus per-document metadata."""

    def __init__(self) -> None:
        self.index: dict[str, dict[str, dict[str, Any]]] = {}
        self.docs: dict[str, dict[str, Any]] = {}

    def add_document(self, url: str, html: str) -> None:
        title, text = extract_text(html)
        tokens = tokenize(text)
        self.docs[url] = {"title": title, "length": len(tokens)}
        for position, term in enumerate(tokens):
            postings = self.index.setdefault(term, {})
            entry = postings.get(url)
            if entry is None:
                postings[url] = {"freq": 1, "positions": [position]}
            else:
                entry["freq"] += 1
                entry["positions"].append(position)

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "docs": self.docs}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Indexer":
        idx = cls()
        idx.index = data.get("index", {})
        idx.docs = data.get("docs", {})
        return idx

    @property
    def num_documents(self) -> int:
        return len(self.docs)

    @property
    def num_terms(self) -> int:
        return len(self.index)
