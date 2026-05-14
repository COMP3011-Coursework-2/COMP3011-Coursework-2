"""Interactive shell for the COMP3011 Coursework 2 search tool."""

from __future__ import annotations

import logging
import shlex
import sys
from pathlib import Path

from crawler import Crawler
from indexer import Indexer
from search import find_pages, load_index, print_postings, save_index

SEED_URL = "https://quotes.toscrape.com/"
INDEX_PATH = Path("data/index.json")
PROMPT = "> "

HELP_TEXT = """Available commands:
  build              Crawl the site, build the inverted index, save to disk.
  load               Load the previously built index from disk.
  print <word>       Print the inverted index entry for one word.
  find <w1> [w2 ..]  List pages containing all of the given words (AND).
  help, ?            Show this help.
  exit, quit         Leave the shell.
"""


class Shell:
    def __init__(self) -> None:
        self.index: Indexer | None = None

    def run(self) -> None:
        while True:
            try:
                raw = input(PROMPT)
            except EOFError:
                print()
                return
            except KeyboardInterrupt:
                print()
                continue

            try:
                parts = shlex.split(raw)
            except ValueError as exc:
                print(f"parse error: {exc}")
                continue
            if not parts:
                continue

            command, args = parts[0].lower(), parts[1:]
            if command in {"exit", "quit"}:
                return
            try:
                self._dispatch(command, args)
            except Exception as exc:  # noqa: BLE001 — REPL must stay alive.
                print(f"error: {exc}")

    def _dispatch(self, command: str, args: list[str]) -> None:
        if command == "build":
            self._build()
        elif command == "load":
            self._load()
        elif command == "print":
            self._print(args)
        elif command == "find":
            self._find(args)
        elif command in {"help", "?"}:
            print(HELP_TEXT, end="")
        else:
            print(f"unknown command: {command!r}. Type 'help' for options.")

    def _build(self) -> None:
        print(f"crawling {SEED_URL} (politeness window 6s) ...")
        crawler = Crawler(SEED_URL)
        indexer = Indexer()
        for n, (url, html) in enumerate(crawler.crawl(), start=1):
            indexer.add_document(url, html)
            print(f"  [{n}] {url}")
        save_index(indexer, INDEX_PATH)
        self.index = indexer
        print(
            f"done — {indexer.num_documents} pages, "
            f"{indexer.num_terms} unique terms → {INDEX_PATH}"
        )

    def _load(self) -> None:
        self.index = load_index(INDEX_PATH)
        print(
            f"loaded {self.index.num_documents} pages, "
            f"{self.index.num_terms} unique terms from {INDEX_PATH}"
        )

    def _print(self, args: list[str]) -> None:
        if self.index is None:
            print("index not loaded — run 'build' or 'load' first.")
            return
        if len(args) != 1:
            print("usage: print <word>")
            return
        print(print_postings(self.index, args[0]))

    def _find(self, args: list[str]) -> None:
        if self.index is None:
            print("index not loaded — run 'build' or 'load' first.")
            return
        if not args:
            print("usage: find <word> [<word> ...]")
            return
        results = find_pages(self.index, args)
        if not results:
            print("no results")
            return
        for url, score in results:
            print(f"{score:.4f}  {url}")


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s"
    )
    Shell().run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
