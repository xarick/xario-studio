"""Tiny in-process rate limiter (no extra dependency / Redis needed).

Used to throttle abuse-prone endpoints — chiefly login, to slow brute-force
guessing. It is a per-process sliding-window counter: good enough for a single
web container, and it fails open (never blocks legitimate traffic beyond the
configured window). Scale-out deployments behind several web replicas should
move this to Redis, but the contract here stays the same.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Allow at most `max_calls` hits per `period` seconds for a given key."""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str) -> None:
        """Record a hit for `key`; raise HTTP 429 if it exceeds the window."""
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            while dq and now - dq[0] > self.period:
                dq.popleft()
            if len(dq) >= self.max_calls:
                retry = int(self.period - (now - dq[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many attempts. Please try again in {retry}s.",
                    headers={"Retry-After": str(retry)},
                )
            dq.append(now)
            # Opportunistic memory hygiene: drop empty buckets occasionally.
            if len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]


def client_ip(request: Request) -> str:
    """Best-effort caller IP, honouring a single proxy's X-Forwarded-For."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
