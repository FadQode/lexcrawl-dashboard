"""A small thread-safe TTL cache for API responses.

Page views share API results for a short window, so the dashboard stays fast and the
LexCrawl API (and its database) see one request per window instead of one per visitor.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable


class TtlCache:
    """Memoise values for a fixed number of seconds."""

    def __init__(self, ttl_seconds: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._clock = clock
        self._entries: dict[Hashable, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_set[T](self, key: Hashable, produce: Callable[[], T]) -> T:
        """Return the cached value for `key`, producing (and caching) it when stale.

        Failures are never cached, so the next request retries the API.
        """
        if self._ttl == 0:
            return produce()
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and now - entry[0] < self._ttl:
                return entry[1]  # type: ignore[return-value]
        value = produce()
        with self._lock:
            self._entries[key] = (self._clock(), value)
        return value

    def clear(self) -> None:
        """Drop every cached value."""
        with self._lock:
            self._entries.clear()
