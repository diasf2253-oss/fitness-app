"""
Tiny in-memory fixed-window rate limiter for the auth endpoints.

The app runs as a single Uvicorn process on one Railway instance with a SQLite
database, so a process-local dict is enough — no Redis. State is not shared
across restarts or workers, which is fine here: this is a brute-force speed
bump, not billing-grade accounting.

Gated on settings.auth_rate_limit_enabled, which conftest.py turns off so the
test suite's many logins don't trip it (test_rate_limit.py flips it back on).
"""
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.config import settings

# "scope:ip" -> monotonic timestamps of recent hits (pruned on each request)
_hits: dict[str, list[float]] = defaultdict(list)


def reset() -> None:
    """Clear every counter. Used by tests to isolate cases."""
    _hits.clear()


def _client_ip(request: Request) -> str:
    # Behind Railway's proxy the real client sits in X-Forwarded-For; take the
    # left-most entry, falling back to the socket peer for local/dev. XFF can
    # be spoofed by a determined attacker, so treat this as a speed bump.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(max_hits: int, window_seconds: int = 60, *, scope: str):
    """Build a FastAPI dependency that allows `max_hits` requests per
    `window_seconds` per client IP for `scope`, raising 429 (with a
    Retry-After header) once the window is full."""

    def dependency(request: Request) -> None:
        if not settings.auth_rate_limit_enabled:
            return
        now = time.monotonic()
        key = f"{scope}:{_client_ip(request)}"
        recent = [t for t in _hits[key] if t > now - window_seconds]
        if len(recent) >= max_hits:
            retry_after = int(window_seconds - (now - recent[0])) + 1
            _hits[key] = recent
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a minute and try again.",
                headers={"Retry-After": str(retry_after)},
            )
        recent.append(now)
        _hits[key] = recent

    return dependency
