from __future__ import annotations

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import Settings, get_settings


class RedisClients:
    """Thin wrapper around shared sync/async Redis clients for the app."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._sync: Redis | None = None
        self._async: AsyncRedis | None = None

    def sync(self) -> Redis:
        if self._sync is None:
            self._sync = Redis.from_url(self.settings.redis_url)
        return self._sync

    def async_redis(self) -> AsyncRedis:
        if self._async is None:
            self._async = AsyncRedis.from_url(self.settings.redis_url)
        return self._async

    def close(self) -> None:
        if self._sync is not None:
            self._sync.close()
            self._sync = None
        if self._async is not None:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async.aclose())
            except RuntimeError:
                asyncio.run(self._async.aclose())
            self._async = None


_clients = RedisClients()


def get_redis() -> Redis:
    """Shared sync Redis client; used by locks and simple state checks."""
    return _clients.sync()


def get_async_redis() -> AsyncRedis:
    """Shared async Redis client; reserved for SSE progress streaming (Phase 7)."""
    return _clients.async_redis()


def close_redis() -> None:
    _clients.close()
