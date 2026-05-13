"""Tests for tokenisation, text extraction, and inverted-index construction."""

from indexer import Indexer, extract_text, tokenize


def test_tokenize_basic():
    assert tokenize("Hello, World!") == ["hello", "world"]


def test_tokenize_empty():
    assert tokenize("") == []


def test_tokenize_whitespace_only():
    assert tokenize("   \n\t  ") == []


def test_tokenize_keeps_numbers():
    assert tokenize("Page 1 of 3") == ["page", "1", "of", "3"]


def test_tokenize_lowercases():
    assert tokenize("GoOd") == ["good"]


def test_tokenize_splits_on_punctuation():
    assert tokenize("don't worry-be happy") == ["don", "t", "worry", "be", "happy"]


def test_extract_text_basic():
    html = "<html><head><title>T</title></head><body>Hello world</body></html>"
    title, text = extract_text(html)
    assert title == "T"
    assert "Hello world" in text


def test_extract_text_strips_script_and_style():
    html = """
    <html><head><title>x</title></head><body>
      <script>alert('boom')</script>
      <style>body { color: red }</style>
      visible
    </body></html>
    """
    _, text = extract_text(html)
    assert "alert" not in text
    assert "color: red" not in text
    assert "visible" in text


def test_extract_text_missing_title():
    title, _ = extract_text("<html><body>Hi</body></html>")
    assert title == ""


def test_extract_text_no_body_falls_back():
    # malformed HTML with no <body> still yields something usable.
    title, text = extract_text("<p>loose paragraph</p>")
    assert "loose paragraph" in text


def test_indexer_single_document_freq_and_positions():
    idx = Indexer()
    idx.add_document("u1", "<html><body>cat dog cat</body></html>")
    assert idx.index["cat"]["u1"]["freq"] == 2
    assert idx.index["cat"]["u1"]["positions"] == [0, 2]
    assert idx.index["dog"]["u1"]["freq"] == 1
    assert idx.index["dog"]["u1"]["positions"] == [1]
    assert idx.docs["u1"]["length"] == 3


def test_indexer_multiple_documents():
    idx = Indexer()
    idx.add_document("u1", "<html><body>good</body></html>")
    idx.add_document("u2", "<html><body>good friend</body></html>")
    assert set(idx.index["good"].keys()) == {"u1", "u2"}
    assert idx.index["friend"]["u2"]["freq"] == 1
    assert idx.num_documents == 2
    assert idx.num_terms == 2


def test_indexer_case_insensitive():
    idx = Indexer()
    idx.add_document("u1", "<html><body>Good GOOD good</body></html>")
    assert idx.index["good"]["u1"]["freq"] == 3
    assert "Good" not in idx.index
    assert "GOOD" not in idx.index


def test_indexer_empty_document():
    idx = Indexer()
    idx.add_document("u1", "<html><body></body></html>")
    assert idx.docs["u1"]["length"] == 0
    assert idx.index == {}


def test_indexer_records_title():
    idx = Indexer()
    idx.add_document("u1", "<html><head><title>Hello</title></head><body>x</body></html>")
    assert idx.docs["u1"]["title"] == "Hello"


def test_indexer_roundtrip_to_dict():
    idx = Indexer()
    idx.add_document("u1", "<html><body>hello world hello</body></html>")
    data = idx.to_dict()
    assert set(data.keys()) == {"index", "docs"}

    other = Indexer.from_dict(data)
    assert other.index == idx.index
    assert other.docs == idx.docs


def test_indexer_from_empty_dict():
    idx = Indexer.from_dict({})
    assert idx.index == {}
    assert idx.docs == {}
    assert idx.num_documents == 0
    assert idx.num_terms == 0
