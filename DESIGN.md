# Design Document — COMP3011 Coursework 2

## 1. Introduction

This project is a small command-line search tool for the website
<https://quotes.toscrape.com/>. It crawls every page on the site,
builds an inverted index of the words it finds, saves the index to
disk, and lets the user search the index from a shell.

The tool exposes four commands: `build`, `load`, `print`, and `find`.

## 2. Features

| Command            | Purpose                                                                 |
| ------------------ | ----------------------------------------------------------------------- |
| `build`            | Crawl the site, build the inverted index, write it to `data/`.          |
| `load`             | Read the saved index back into memory.                                  |
| `print <word>`     | Print the inverted index entry for a single word.                       |
| `find <w1> <w2> …` | Return the list of pages that contain *all* of the given query words.   |

Other behaviour:

- Searches are case-insensitive (`Good` == `good`).
- Multi-word `find` queries are treated as a conjunction (AND).
- Empty queries, unknown words, and network errors are handled without crashing.

## 3. Architecture

Three modules, each with a single responsibility, plus a thin CLI layer:

| Module        | Responsibility                                  |
| ------------- | ----------------------------------------------- |
| `main.py`     | Argument parsing, REPL loop                     |
| `crawler.py`  | Fetch pages, follow links (BFS)                 |
| `indexer.py`  | Tokenise, normalise, build inverted index       |
| `search.py`   | Load index, run `print` / `find` queries        |

### 3.1 Crawler (`crawler.py`)

- **Algorithm.** Breadth-first traversal starting from the seed URL
  `https://quotes.toscrape.com/`. A `frontier` queue holds URLs still
  to visit; a `visited` set prevents re-fetching.
- **Scope.** Only follow links whose host matches the seed host;
  external links are recorded but not crawled.
- **Politeness.** A minimum 6-second delay between successive HTTP
  requests, as required by the brief. Implemented by recording the
  timestamp of the last request and sleeping the remainder of the
  window before the next one.
- **HTTP.** `requests` with a custom `User-Agent`, a request timeout,
  and a small retry-with-backoff for transient failures (timeouts,
  5xx). 4xx responses are logged and skipped.
- **Parsing.** `BeautifulSoup` (lxml parser) extracts visible text and
  outbound `<a href>` links.

### 3.2 Indexer (`indexer.py`)

- **Tokenisation.** Lower-case the page text, split on non-alphanumeric
  characters, drop empty tokens.
- **Inverted index structure.**

```python
  index: dict[str, dict[str, dict]] = {
      "good": {
          "https://quotes.toscrape.com/page/1/": {
              "freq": 3,
              "positions": [12, 47, 102],
          },
          ...
      },
      ...
  }
```

  A `dict` of term → `dict` of URL → `{freq, positions}`. This gives
  O(1) lookup by term and by document, and storing positions leaves
  room for phrase queries or proximity ranking later.

- **Document metadata.** A parallel `dict` of URL → `{title, length}`
  is kept for display in search results.

### 3.3 Storage (`build` / `load`)

The whole index is serialised to a single JSON file at
`data/index.json`. JSON is chosen over `pickle` because it is
human-readable (helpful when marking and debugging) and not tied to
a Python version. The index is small enough that load time is not
a concern.

### 3.4 Search (`search.py`)

- **`print <word>`** — look the word up in the index and print its
  inverted index entry (postings: URL, frequency, positions).
- **`find <w1> <w2> …`** — look up each word, intersect the sets of
  URLs in their postings, score each matched URL by TF-IDF, and print
  results in descending score order. An empty intersection prints a
  friendly "no results" message.
- **Edge cases handled:** word not in index, empty query, query with
  only whitespace, mixed case, repeated query terms (deduplicated).

#### Ranking — TF-IDF

For each matched document $d$ and query $q$:

$$
\operatorname{TF}(t, d) = \frac{\operatorname{freq}(t, d)}{\operatorname{length}(d)}
\qquad
\operatorname{IDF}(t) = \ln\!\left(\frac{N}{\operatorname{df}(t)}\right)
$$

$$
\operatorname{score}(q, d) = \sum_{t \in q} \operatorname{TF}(t, d) \cdot \operatorname{IDF}(t)
$$

where $N$ is the number of indexed documents, $\operatorname{df}(t)$ is the
number of documents containing $t$, $\operatorname{freq}(t, d)$ is the term
frequency in $d$, and $\operatorname{length}(d)$ is the document's token
count.

- **Length normalization** prevents bias toward long documents (a 1000-
  word page would otherwise dominate a 50-word page with the same
  proportional usage).
- **Classic (unsmoothed) IDF** is chosen because for a 50-page corpus
  it is the most transparent formula, and smoothing's only practical
  benefit — guarding against $\operatorname{df}(t) = 0$ — is
  unreachable: `find_pages` early-returns `[]` if any query term has
  no postings, so by the time IDF is computed every term has
  $\operatorname{df}(t) \geq 1$.
- **Ties** (equal scores, e.g. when every query term has
  $\operatorname{df}(t) = N$) are broken alphabetically by URL so
  output is deterministic.
- **No format change.** Every statistic needed ($N$,
  $\operatorname{df}$, $\operatorname{freq}$, $\operatorname{length}$)
  is already in the existing index, so adding ranking did not require
  re-crawling or modifying `data/index.json`.

## 4. Technical Stack

- **Language:** Python 3.11+
- **Libraries:** `requests` (HTTP), `beautifulsoup4` + `lxml` (HTML
  parsing), `pytest` (tests), `pytest-cov` (coverage).
- **Standard library:** `json`, `collections`, `urllib.parse`, `time`,
  `argparse`.

## 5. Repository Structure

```txt
COMP3011-Coursework-2/
├── src/
│   ├── crawler.py
│   ├── indexer.py
│   ├── search.py
│   └── main.py
├── tests/
│   ├── test_crawler.py
│   ├── test_indexer.py
│   └── test_search.py
├── data/
│   └── index.json          # produced by `build`
├── requirements.txt
└── README.md
```

## 6. Testing

- **Framework:** `pytest`, run with `pytest --cov=src tests/`.
- **Crawler tests** use `responses` or `unittest.mock` to fake HTTP
  so tests are fast, deterministic, and respect the real site (no
  live requests in CI).
- **Indexer tests** feed in small fixed HTML snippets and assert on
  the resulting index — easy to reason about, covers tokenisation,
  case-folding, and frequency counting.
- **Search tests** build a tiny in-memory index and check `print` and
  `find` on: single word, multi-word AND, missing word, empty query,
  mixed case.
- **Coverage target:** 100 %.

## 7. Code Style & Quality

- Follow PEP 8 as a style guideline.
- Type hints on public functions.
- Module- and function-level docstrings.
- Functions kept small and single-purpose; no module over ~200 lines.

## 8. Version Control

- Git, hosted on GitHub.
- Linear history on `main` with small, focused commits and descriptive
  messages. No feature branches — the project is small enough that
  branching adds overhead without benefit.
- One commit per logical change, not per file save.

## 9. Documentation

`README.md` will cover:

- What the project is and which site it targets.
- Setup: `python -m venv`, `pip install -r requirements.txt`.
- Usage: a worked example for each of the four commands.
- How to run the tests and view coverage.
- Brief architecture overview (link back to this design doc).

## Acknowledgement

This design is written with assistance from Generative AI.
