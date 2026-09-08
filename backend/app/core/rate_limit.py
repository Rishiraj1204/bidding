import time
from collections import defaultdict
from typing import Dict, List, Tuple
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import logger


class RateLimiter:
    """In-memory sliding window rate limiter per client IP."""
    def __init__(self):
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._failed_logins: Dict[str, List[float]] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}

    def is_rate_limited(self, client_ip: str, limit: int = 120, window_seconds: int = 60) -> bool:
        """Check if client IP has exceeded the request threshold."""
        now = time.time()
        window_start = now - window_seconds

        # Clean old timestamps
        timestamps = [t for t in self._requests[client_ip] if t > window_start]
        self._requests[client_ip] = timestamps

        if len(timestamps) >= limit:
            return True

        self._requests[client_ip].append(now)
        return False

    def record_failed_login(self, identifier: str) -> bool:
        """Record a failed login attempt; returns True if account/IP is now locked out."""
        now = time.time()
        window_start = now - (settings.AUTH_LOCKOUT_MINUTES * 60)

        attempts = [t for t in self._failed_logins[identifier] if t > window_start]
        attempts.append(now)
        self._failed_logins[identifier] = attempts

        if len(attempts) >= settings.AUTH_MAX_FAILED_ATTEMPTS:
            self._lockouts[identifier] = now + (settings.AUTH_LOCKOUT_MINUTES * 60)
            logger.warning(f"Brute force protection triggered: Lockout applied to {identifier}")
            return True
        return False

    def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        """Check if identifier is temporarily locked out. Returns (is_locked, seconds_remaining)."""
        lock_expiry = self._lockouts.get(identifier, 0)
        now = time.time()
        if lock_expiry > now:
            return True, int(lock_expiry - now)
        elif identifier in self._lockouts:
            del self._lockouts[identifier]
        return False, 0

    def reset_failed_logins(self, identifier: str):
        """Reset failed login attempts upon successful authentication."""
        self._failed_logins.pop(identifier, None)
        self._lockouts.pop(identifier, None)


limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware applying rate limits per IP address."""
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # Skip rate limiting for internal health checks
        if request.url.path in {"/health", "/api/v1/health", "/"}:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # In testing environments or local test client, don't throttle
        if client_ip in {"testclient"}:
            return await call_next(request)

        if limiter.is_rate_limited(client_ip, limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please slow down and retry shortly."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
