"""Tests for index persistence and query execution."""

import json

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
    assert find_pages(sample_index, ["good"]) == ["https://a/", "https://b/"]


def test_find_multi_word_intersects(sample_index):
    assert find_pages(sample_index, ["good", "friend"]) == ["https://a/"]


def test_find_no_overlap_returns_empty(sample_index):
    assert find_pages(sample_index, ["good", "bad"]) == []


def test_find_missing_word_returns_empty(sample_index):
    assert find_pages(sample_index, ["zzz"]) == []


def test_find_empty_query_returns_empty(sample_index):
    assert find_pages(sample_index, []) == []


def test_find_whitespace_only_returns_empty(sample_index):
    assert find_pages(sample_index, ["   ", "\t"]) == []


def test_find_is_case_insensitive(sample_index):
    assert find_pages(sample_index, ["GOOD", "FRIEND"]) == ["https://a/"]
