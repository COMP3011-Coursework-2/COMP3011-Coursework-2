# Testing Document — COMP3011 Coursework 2

## 1. Goals

The test suite has three jobs:

1. **Correctness** — verify that each module behaves as documented in
   [DESIGN.md](DESIGN.md) (tokenisation, BFS crawl order, TF-IDF
   ranking, REPL dispatch).
2. **Determinism** — the suite must not depend on the network, the
   clock, or the live <https://quotes.toscrape.com/> site. Every test
   should produce the same result on every machine.
3. **Regression safety** — every public function and every code path
   reachable from the REPL is exercised, so future edits are caught by
   a failing test rather than by a runtime surprise.

## 2. Framework and Tooling

| Tool         | Purpose                                       |
| ------------ | --------------------------------------------- |
| `pytest`     | Test runner and assertion engine              |
| `pytest-cov` | Line-coverage reporting                       |
| `unittest.mock` | Patching HTTP, time, and `builtins.input` |

No third-party HTTP-mocking library is needed; `MagicMock` on the
`requests.Session.get` attribute is sufficient and avoids an extra
dependency.

## 3. Repository Layout

```txt
tests/
├── conftest.py        # makes src/ importable by module name
├── test_crawler.py    # BFS, politeness, retries, host scoping
├── test_indexer.py    # tokenisation, text extraction, index build
├── test_search.py     # save/load, print, find, TF-IDF ranking
└── test_main.py       # REPL dispatch, guards, error recovery
```

`conftest.py` prepends `src/` to `sys.path` so tests can `from crawler
import Crawler` rather than `from src.crawler import Crawler`. This
keeps imports identical to the way the modules import each other.

## 4. Running the Tests

Activate the Conda environment and run from the project root:

```sh
conda activate COMP3011-Coursework-2
pytest tests/
```

With coverage:

```sh
pytest --cov=src --cov-report=term-missing tests/
```

Current result:

```text
collected 69 items

tests/test_crawler.py ..............    [ 20%]
tests/test_indexer.py .................  [ 44%]
tests/test_main.py ....................  [ 73%]
tests/test_search.py ..................  [100%]

Name             Stmts   Miss  Cover   Missing
----------------------------------------------
src/crawler.py      85      0   100%
src/indexer.py      45      0   100%
src/main.py         89      0   100%
src/search.py       49      0   100%
----------------------------------------------
TOTAL              268      0   100%
69 passed in 0.22s
```

The whole suite finishes in well under a second because no real
network I/O or `time.sleep` happens.

## 5. Strategy by Module

### 5.1 Crawler (`test_crawler.py`, 14 tests)

The crawler is the only module that touches the network, so the
testing strategy here is the most involved.

- **HTTP is fully mocked.** Each test installs a `MagicMock` on
  `Crawler.session.get` that returns a fake `Response`-shaped object
  built by the `make_response` helper. Tests never reach the real
  site, and the brief's 6-second politeness rule is honoured by
  default in production code, not by sleeping during tests.
- **`time.sleep` is patched out** by an autouse fixture
  (`_no_real_sleep`) so tests are fast even when the production code
  asks to wait six seconds between requests.
- **Cases covered:**
  - URL normalisation (fragments stripped; seed normalised at
    construction).
  - Happy paths: seed-only crawl; BFS over multiple in-host links;
    deduplication of repeated links.
  - Scope: out-of-host links are recorded but not followed.
  - Failure handling: 404 is skipped without retry; non-HTML
    `Content-Type` is skipped; 5xx retries and then either succeeds
    or exhausts the retry budget; `requests.Timeout` and
    `requests.ConnectionError` follow the same retry policy.
  - Politeness: `time.sleep` is called between requests with the
    configured delay, but **not** before the very first request.

### 5.2 Indexer (`test_indexer.py`, 17 tests)

Pure-function territory, so testing is direct: small fixed HTML
strings in, assertions on the resulting `index`/`docs` dictionaries
out.

- **Tokenisation:** basic split, empty input, whitespace-only input,
  case-folding, splitting on punctuation, retention of numeric
  tokens.
- **Text extraction:** title parsed; `<script>` and `<style>`
  contents stripped from the body text; missing `<title>`; malformed
  HTML without a `<body>` falls back gracefully.
- **Index build:** term frequency and position lists for a single
  document; multi-document postings; case-insensitive aggregation;
  empty document yields empty index; titles recorded on the docs
  map; `to_dict` / `from_dict` round-trip; `from_dict({})` yields an
  empty indexer.

### 5.3 Search (`test_search.py`, 18 tests)

Builds tiny in-memory `Indexer` instances via a `sample_index`
fixture so each test asserts on a known corpus.

- **Persistence:** `save_index` then `load_index` round-trip equals
  the original `index`/`docs`; missing parent directories are
  created on save; loading a non-existent file raises
  `FileNotFoundError`.
- **`print_postings`:** existing word formatted correctly;
  case-insensitive lookup; missing word produces a friendly
  message rather than an exception.
- **`find_pages` mechanics:** single-word query; multi-word
  intersection (AND semantics); zero overlap returns `[]`; missing
  word returns `[]`; empty query returns `[]`; whitespace-only
  query returns `[]`; case-insensitive lookup; query terms are
  deduplicated (e.g. `["good", "GOOD", "good"]` equals `["good"]`).
- **TF-IDF ranking:** scores are checked against hand-computed
  values (`(freq/length) · ln(N/df)`). Dedicated cases verify that:
  higher term frequency outranks lower; length normalisation gives a
  shorter document a higher score for the same raw frequency; a
  rarer term contributes more than a term that appears in every
  document (IDF = 0); ties break alphabetically by URL so output is
  deterministic.

### 5.4 REPL (`test_main.py`, 20 tests)

The REPL is exercised by calling `Shell()._dispatch` directly for
single-command tests, and by patching `builtins.input` with
`side_effect=[...]` for tests of the `run()` loop.

- **Help / unknown commands:** `help` and its `?` alias list the four
  commands; unknown commands print a clear message.
- **Guards:** `print` and `find` refuse to run before an index is
  loaded.
- **Usage errors:** `print` with zero or more than one argument,
  `find` with no arguments — each emits a "usage" message.
- **Happy-path dispatch:** `print <word>` and `find <word>` produce
  the expected output; `find` with no matches prints `no results`.
- **`load`:** reads a previously saved index from `INDEX_PATH` (which
  is monkey-patched to a `tmp_path` so the real `data/index.json` is
  never touched).
- **`build`:** the real `Crawler` is replaced by a `FakeCrawler` whose
  `crawl()` yields a fixed list of `(url, html)` tuples, so `build`
  can be tested without any HTTP calls; the resulting index is then
  asserted on disk and in memory.
- **`run()` loop:** clean exit on `EOF`; clean exit on `quit`;
  `KeyboardInterrupt` is swallowed and the loop continues; a command
  that raises is reported as `error: ...` and the loop keeps going;
  blank lines are skipped; a `shlex` parse error (e.g.
  `'"unterminated`) prints `parse error` rather than crashing.
- **`main()` entry point** returns `0` on a clean EOF.

## 6. Mocking Conventions

| Concern              | How it is faked                                    |
| -------------------- | -------------------------------------------------- |
| HTTP                 | `MagicMock` on `Crawler.session.get`               |
| Politeness sleep     | `monkeypatch.setattr("crawler.time.sleep", ...)`   |
| Wall clock           | `monkeypatch.setattr("crawler.time.monotonic", ...)`|
| User input           | `patch("builtins.input", side_effect=[...])`       |
| Index file location  | `monkeypatch.setattr(main_module, "INDEX_PATH", tmp_path / ...)` |
| Crawler in `build`   | `monkeypatch.setattr(main_module, "Crawler", FakeCrawler)` |

These conventions mean **no test reads from the network, sleeps, or
writes outside `tmp_path`**, so the suite is safe to run in CI and
on the marker's machine without side effects.

## 7. Coverage Policy

- **Target:** 100% line coverage on `src/`.
- **Current:** 100% (268 / 268 statements; see §4).
- **Why 100%:** the codebase is small enough that any unexercised
  line is almost certainly dead code or an untested branch worth
  catching. Coverage is *not* a substitute for thinking about edge
  cases — the test cases above are chosen for behaviour, and 100%
  coverage falls out as a consequence rather than being the goal.

## 8. Acknowledgement

This testing document was written with assistance from Generative AI.
