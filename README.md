# COMP3011 Coursework 2 — Search Engine Tool

A small command-line search tool for [quotes.toscrape.com](https://quotes.toscrape.com/).
It crawls the site, builds an inverted index of every word it sees, writes the
index to disk, and lets you query it from an interactive shell.

## Setup

Requires Python 3.11 or newer.

```sh
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Dependencies

Installed by the `pip install` step above; pinned in [requirements.txt](requirements.txt).

| Package           | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `requests`        | HTTP client for the crawler                      |
| `beautifulsoup4`  | HTML parsing                                     |
| `lxml`            | Fast parser backend for BeautifulSoup            |
| `pytest`          | Test runner                                      |
| `pytest-cov`      | Coverage reporting                               |

## Usage

Start the shell:

```sh
python src/main.py
```

The shell exposes four commands.

### `build`

Crawls the site and writes the index to `data/index.json`. The crawl observes
a 6-second politeness window between requests, so it takes ~5 minutes.

```text
> build
crawling https://quotes.toscrape.com/ (politeness window 6s) ...
  [1] https://quotes.toscrape.com/
  [2] https://quotes.toscrape.com/page/2/
  ...
done — 50 pages, 2914 unique terms → data/index.json
```

### `load`

Reads a previously built index from disk into memory.

```text
> load
loaded 50 pages, 2914 unique terms from data/index.json
```

### `print <word>`

Prints the inverted-index entry for one word (case-insensitive). Each posting
shows the page URL, the term frequency, and the token positions.

```text
> print nonsense
nonsense: 1 document(s)
  https://quotes.toscrape.com/page/3/  freq=1  positions=[214]
```

### `find <word> [<word> ...]`

Returns the pages containing **all** the given words (conjunctive AND query),
ranked by descending TF-IDF score. Each line shows the score and the URL.

```text
> find indifference
0.2172  https://quotes.toscrape.com/tag/indifference/page/1/
0.1810  https://quotes.toscrape.com/tag/activism/page/1/
0.1810  https://quotes.toscrape.com/tag/apathy/page/1/
...

> find good friends
0.0817  https://quotes.toscrape.com/tag/contentment/page/1/
0.0724  https://quotes.toscrape.com/tag/good/page/1/
0.0351  https://quotes.toscrape.com/tag/aliteracy/page/1/
...
```

The score uses length-normalized TF and classic IDF,
$\mathrm{score}(q, d) = \sum_{t \in q} \frac{\mathrm{freq}(t, d)}{\mathrm{length}(d)} \cdot \ln\!\left(\frac{N}{\mathrm{df}(t)}\right)$;
see [DESIGN.md](DESIGN.md) §3.4 for the rationale. If any word is absent from the index, or the query is empty,
the shell prints `no results`.

Type `help` for the in-shell command list, or `exit` to quit.

## Architecture

Four modules with single responsibilities:

| Module          | Role                                              |
| --------------- | ------------------------------------------------- |
| `crawler.py`    | Polite BFS crawler over a single host             |
| `indexer.py`    | Tokenisation and inverted-index construction      |
| `search.py`     | Index persistence (JSON) and query execution      |
| `main.py`       | Interactive shell                                 |

See [DESIGN.md](DESIGN.md) for the full design rationale.

## Testing

The test suite lives under [tests/](tests/) and uses `pytest`. From the
project root:

```sh
pytest tests/
```

With coverage:

```sh
pytest --cov=src --cov-report=term-missing tests/
```

The suite has 69 tests covering the crawler (HTTP fully mocked), indexer,
search, and REPL dispatch, and reports 100% line coverage. See
[TESTING.md](TESTING.md) for the full strategy, per-module breakdown, and
mocking conventions.

## Acknowledgement

Developed with assistance from Generative AI; see the video demonstration for
the GenAI critical evaluation.
