"""Polite breadth-first crawler for a single host."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Iterator
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "COMP3011-Coursework-Bot/1.0 (+student project)"


def _normalise(url: str) -> str:
    """Strip fragment and collapse a trailing slash on the path root only."""
    url, _ = urldefrag(url)
    return url


class Crawler:
    """BFS crawler restricted to the seed URL's host.

    Yields ``(url, html)`` for each successfully fetched HTML page. Enforces a
    minimum delay between successive HTTP requests (politeness window).
    """

    def __init__(
        self,
        seed_url: str,
        *,
        delay: float = 6.0,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self.seed_url = _normalise(seed_url)
        self.host = urlparse(self.seed_url).netloc
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_fetch_ts: float | None = None

    def crawl(self) -> Iterator[tuple[str, str]]:
        frontier: deque[str] = deque([self.seed_url])
        visited: set[str] = {self.seed_url}

        while frontier:
            url = frontier.popleft()
            html = self._fetch(url)
            if html is None:
                continue
            yield url, html

            for link in self._extract_links(url, html):
                if link not in visited and self._in_scope(link):
                    visited.add(link)
                    frontier.append(link)

    def _in_scope(self, url: str) -> bool:
        return urlparse(url).netloc == self.host

    def _wait_for_politeness(self) -> None:
        if self._last_fetch_ts is None:
            return
        elapsed = time.monotonic() - self._last_fetch_ts
        remaining = self.delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _fetch(self, url: str) -> str | None:
        """Fetch a URL with retries. Returns HTML body or None on failure."""
        backoff = 1.0
        for attempt in range(1, self.max_retries + 1):
            self._wait_for_politeness()
            try:
                response = self.session.get(url, timeout=self.timeout)
                self._last_fetch_ts = time.monotonic()
            except (requests.Timeout, requests.ConnectionError) as exc:
                log.warning("attempt %d: %s for %s", attempt, exc, url)
                self._last_fetch_ts = time.monotonic()
                if attempt == self.max_retries:
                    return None
                time.sleep(backoff)
                backoff *= 2
                continue

            status = response.status_code
            if status == 200:
                content_type = response.headers.get("Content-Type", "")
                if "html" not in content_type.lower():
                    log.info("skipping non-HTML %s (%s)", url, content_type)
                    return None
                return response.text
            if 500 <= status < 600:
                log.warning("attempt %d: HTTP %d for %s", attempt, status, url)
                if attempt == self.max_retries:
                    return None
                time.sleep(backoff)
                backoff *= 2
                continue
            log.info("skipping %s — HTTP %d", url, status)
            return None
        return None  # pragma: no cover  -- unreachable; loop always returns

    def _extract_links(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        out: list[str] = []
        for anchor in soup.find_all("a", href=True):
            absolute = urljoin(base_url, anchor["href"])
            absolute = _normalise(absolute)
            if absolute.startswith(("http://", "https://")):
                out.append(absolute)
        return out
