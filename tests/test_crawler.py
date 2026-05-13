"""Tests for the polite BFS crawler — HTTP is fully mocked."""

from unittest.mock import MagicMock

import pytest
import requests

from crawler import Crawler, _normalise


def make_response(text: str = "<html><body></body></html>",
                  status: int = 200,
                  content_type: str = "text/html"):
    response = MagicMock()
    response.status_code = status
    response.headers = {"Content-Type": content_type}
    response.text = text
    return response


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Replace time.sleep so tests never actually wait."""
    monkeypatch.setattr("crawler.time.sleep", lambda _s: None)


# --- normalisation -------------------------------------------------------


def test_normalise_strips_fragment():
    assert _normalise("https://example.com/page#top") == "https://example.com/page"


def test_seed_url_normalised_at_construction():
    c = Crawler("https://example.com/#frag", delay=0)
    assert c.seed_url == "https://example.com/"


# --- happy path ---------------------------------------------------------


def test_crawler_yields_seed_only_when_no_links():
    c = Crawler("https://example.com/", delay=0)
    c.session.get = MagicMock(return_value=make_response("<html><body>hi</body></html>"))

    results = list(c.crawl())
    assert [u for u, _ in results] == ["https://example.com/"]


def test_crawler_follows_in_host_links_bfs():
    c = Crawler("https://example.com/", delay=0)
    pages = {
        "https://example.com/": '<html><body><a href="/p2">p2</a><a href="/p3">p3</a></body></html>',
        "https://example.com/p2": "<html><body>two</body></html>",
        "https://example.com/p3": "<html><body>three</body></html>",
    }

    def fake_get(url, *, timeout):
        return make_response(pages[url])

    c.session.get = MagicMock(side_effect=fake_get)
    urls = [u for u, _ in c.crawl()]
    assert urls == [
        "https://example.com/",
        "https://example.com/p2",
        "https://example.com/p3",
    ]


def test_out_of_host_links_are_not_followed():
    c = Crawler("https://example.com/", delay=0)
    html = (
        '<html><body>'
        '<a href="https://other.com/x">x</a>'
        '<a href="https://example.com/inside">inside</a>'
        '</body></html>'
    )

    def fake_get(url, *, timeout):
        if url == "https://example.com/":
            return make_response(html)
        return make_response("<html><body>i</body></html>")

    c.session.get = MagicMock(side_effect=fake_get)
    urls = [u for u, _ in c.crawl()]
    assert "https://other.com/x" not in urls
    assert urls == ["https://example.com/", "https://example.com/inside"]


def test_links_deduplicated():
    c = Crawler("https://example.com/", delay=0)
    html = '<html><body><a href="/a">a</a><a href="/a">a again</a></body></html>'

    def fake_get(url, *, timeout):
        if url == "https://example.com/":
            return make_response(html)
        return make_response("<html><body></body></html>")

    c.session.get = MagicMock(side_effect=fake_get)
    urls = [u for u, _ in c.crawl()]
    assert urls.count("https://example.com/a") == 1


# --- non-success responses ----------------------------------------------


def test_404_is_skipped_without_retry():
    c = Crawler("https://example.com/", delay=0)
    c.session.get = MagicMock(return_value=make_response(status=404))

    assert list(c.crawl()) == []
    assert c.session.get.call_count == 1


def test_non_html_content_type_skipped():
    c = Crawler("https://example.com/", delay=0)
    c.session.get = MagicMock(return_value=make_response(content_type="application/json"))

    assert list(c.crawl()) == []


# --- retry behaviour ----------------------------------------------------


def test_5xx_retries_then_succeeds():
    c = Crawler("https://example.com/", delay=0, max_retries=3)
    c.session.get = MagicMock(side_effect=[
        make_response(status=500),
        make_response(status=503),
        make_response("<html><body>ok</body></html>"),
    ])

    results = list(c.crawl())
    assert len(results) == 1
    assert c.session.get.call_count == 3


def test_5xx_exhausts_retries_then_skips():
    c = Crawler("https://example.com/", delay=0, max_retries=2)
    c.session.get = MagicMock(return_value=make_response(status=500))

    assert list(c.crawl()) == []
    assert c.session.get.call_count == 2


def test_timeout_then_success():
    c = Crawler("https://example.com/", delay=0, max_retries=3)
    c.session.get = MagicMock(side_effect=[
        requests.Timeout("slow"),
        make_response("<html><body>ok</body></html>"),
    ])

    results = list(c.crawl())
    assert len(results) == 1
    assert c.session.get.call_count == 2


def test_connection_error_exhausts_retries():
    c = Crawler("https://example.com/", delay=0, max_retries=2)
    c.session.get = MagicMock(side_effect=requests.ConnectionError("nope"))

    assert list(c.crawl()) == []
    assert c.session.get.call_count == 2


# --- politeness ---------------------------------------------------------


def test_politeness_sleeps_between_requests(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("crawler.time.sleep", lambda s: sleeps.append(s))
    # Freeze monotonic so elapsed == 0 on every call; remaining == delay.
    monkeypatch.setattr("crawler.time.monotonic", lambda: 0.0)

    c = Crawler("https://example.com/", delay=6.0)
    pages = {
        "https://example.com/": '<html><body><a href="/p2">p2</a></body></html>',
        "https://example.com/p2": "<html><body></body></html>",
    }
    c.session.get = MagicMock(side_effect=lambda url, *, timeout: make_response(pages[url]))

    list(c.crawl())
    assert sleeps == [6.0]


def test_no_sleep_before_first_request(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("crawler.time.sleep", lambda s: sleeps.append(s))

    c = Crawler("https://example.com/", delay=6.0)
    c.session.get = MagicMock(return_value=make_response("<html><body></body></html>"))

    list(c.crawl())
    assert sleeps == []
