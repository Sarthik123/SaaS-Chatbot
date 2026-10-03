"""Small safety helpers: a rate limiter and a way to identify visitors without storing their IP.

The rate limiter keeps its counts in memory (one running API process). That is enough for the
free-tier demo. With several API processes each would count separately, which is a known
limit listed in docs/SECURITY-AND-PRIVACY.md.
"""

import hashlib
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request


class RateLimiter:
    """Allow at most `max_events` per `window_seconds` for each key (a "sliding window")."""

    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record one event for `key` and return True, or return False when over the limit."""
        now = self._clock()
        with self._lock:
            self._forget_old(now)
            events = self._events.setdefault(key, deque())
            if len(events) >= self.max_events:
                return False
            events.append(now)
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may send again (0 when it may send now)."""
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if not events or len(events) < self.max_events:
                return 0
            return max(1, int(events[0] + self.window_seconds - now) + 1)

    def _forget_old(self, now: float) -> None:
        cutoff = now - self.window_seconds
        for key in list(self._events):
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]


def hash_ip(ip: str, salt: str) -> str:
    """A one-way, salted fingerprint of an IP address. The raw address is never stored."""
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def client_ip(request: Request, trust_proxy_headers: bool) -> str:
    """The visitor's address. Behind a trusted proxy it is in X-Forwarded-For (first entry)."""
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
