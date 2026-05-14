"""Tests for index persistence and query execution."""

import json
import math

import pytest

from indexer import Indexer
from search import find_pages, load_index, print_postings, save_index


@pytest.fixture
def sample_index() -> Indexer:
    idx = Indexer()
    idx.add_document("https://a/", "<html><body>good friend cat</body></html>")
    idx.add_document("https://b/", "<html><body>good dog</body></html>")
    idx.add_document("https://c/", "<html><body>bad</body></html>")
    return idx


# --- save / load ---------------------------------------------------------


def test_save_and_load_roundtrip(tmp_path, sample_index):
    path = tmp_path / "idx.json"
    save_index(sample_index, path)
    assert path.exists()

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert set(on_disk.keys()) == {"index", "docs"}

    loaded = load_index(path)
    assert loaded.index == sample_index.index
    assert loaded.docs == sample_index.docs


def test_save_creates_missing_parent_dirs(tmp_path, sample_index):
    path = tmp_path / "deeply" / "nested" / "idx.json"
    save_index(sample_index, path)
    assert path.exists()


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_index(tmp_path / "nope.json")


# --- print ---------------------------------------------------------------


def test_print_postings_existing_word(sample_index):
    out = print_postings(sample_index, "good")
    assert out.startswith("good:")
    assert "https://a/" in out
    assert "https://b/" in out
    assert "freq=1" in out


def test_print_postings_is_case_insensitive(sample_index):
    assert print_postings(sample_index, "good") == print_postings(sample_index, "GOOD")


def test_print_postings_missing_word(sample_index):
    out = print_postings(sample_index, "zzz")
    assert "not in the index" in out


# --- find ----------------------------------------------------------------


def test_find_single_word(sample_index):
    # "good" is in a/ (length 3) and b/ (length 2), df=2, N=3 → IDF=ln(3/2).
    # Score a = (1/3)·ln(3/2);  score b = (1/2)·ln(3/2)  →  b ranks first.
    idf = math.log(3 / 2)
    results = find_pages(sample_index, ["good"])
    assert [url for url, _ in results] == ["https://b/", "https://a/"]
    assert results[0][1] == pytest.approx(idf / 2)
    assert results[1][1] == pytest.approx(idf / 3)


def test_find_multi_word_intersects(sample_index):
    results = find_pages(sample_index, ["good", "friend"])
    assert [url for url, _ in results] == ["https://a/"]
    assert results[0][1] > 0


def test_find_no_overlap_returns_empty(sample_index):
    assert find_pages(sample_index, ["good", "bad"]) == []


def test_find_missing_word_returns_empty(sample_index):
    assert find_pages(sample_index, ["zzz"]) == []


def test_find_empty_query_returns_empty(sample_index):
    assert find_pages(sample_index, []) == []


def test_find_whitespace_only_returns_empty(sample_index):
    assert find_pages(sample_index, ["   ", "\t"]) == []


def test_find_is_case_insensitive(sample_index):
    results = find_pages(sample_index, ["GOOD", "FRIEND"])
    assert [url for url, _ in results] == ["https://a/"]


# --- tf-idf ranking ------------------------------------------------------


def test_find_ranks_higher_tf_first():
    idx = Indexer()
    idx.add_document("https://a/", "<html><body>cat cat cat dog dog</body></html>")
    idx.add_document("https://b/", "<html><body>cat dog dog dog dog</body></html>")
    # both length 5; "cat" freq 3 in a vs 1 in b → a ranks first.
    results = find_pages(idx, ["cat"])
    assert [url for url, _ in results] == ["https://a/", "https://b/"]


def test_find_length_normalizes():
    idx = Indexer()
    idx.add_document("https://short/", "<html><body>cat dog</body></html>")
    idx.add_document(
        "https://long/", "<html><body>cat dog dog dog dog dog</body></html>"
    )
    # Third doc without "cat" so df=2 < N=3 and IDF > 0.
    idx.add_document("https://other/", "<html><body>fox</body></html>")
    # "cat" freq 1 in both matched docs; shorter doc has higher TF.
    results = find_pages(idx, ["cat"])
    assert [url for url, _ in results] == ["https://short/", "https://long/"]
    assert results[0][1] > results[1][1]


def test_find_rare_term_contributes_more():
    idx = Indexer()
    # "common" appears in all three docs (IDF=0); "rare" only in a/.
    idx.add_document("https://a/", "<html><body>common rare</body></html>")
    idx.add_document("https://b/", "<html><body>common filler</body></html>")
    idx.add_document("https://c/", "<html><body>common filler</body></html>")
    # Query "common" alone: every doc matches but IDF=0 → all scores 0,
    # alphabetical tie-break gives a, b, c.
    flat = find_pages(idx, ["common"])
    assert [url for url, _ in flat] == ["https://a/", "https://b/", "https://c/"]
    assert all(score == 0.0 for _, score in flat)
    # Query "common rare": only a/ matches and gets a positive score.
    ranked = find_pages(idx, ["common", "rare"])
    assert [url for url, _ in ranked] == ["https://a/"]
    assert ranked[0][1] > 0


def test_find_ties_break_alphabetically():
    idx = Indexer()
    idx.add_document("https://b/", "<html><body>cat dog</body></html>")
    idx.add_document("https://a/", "<html><body>cat dog</body></html>")
    # Identical content → identical scores → URL-sorted output.
    results = find_pages(idx, ["cat"])
    assert [url for url, _ in results] == ["https://a/", "https://b/"]
    assert results[0][1] == pytest.approx(results[1][1])


def test_find_dedupes_query_terms(sample_index):
    once = find_pages(sample_index, ["good"])
    twice = find_pages(sample_index, ["good", "GOOD", "good"])
    assert once == twice
