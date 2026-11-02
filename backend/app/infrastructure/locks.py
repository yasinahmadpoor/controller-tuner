from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def system_ga_lock_key(system_id: UUID | str) -> str:
    return f"lock:system:{system_id}:ga"


class RedisLock:
    """Token-safe distributed lock backed by Redis ``SET NX EX``."""

    def __init__(self, redis: Any, key: str, ttl_seconds: int):
        self._redis = redis
        self.key = key
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.token: str | None = None

    def acquire(self) -> str | None:
        token = uuid.uuid4().hex
        acquired = self._redis.set(self.key, token, nx=True, ex=self.ttl_seconds)
        if acquired:
            self.token = token
            return token
        return None

    def release(self, token: str | None = None) -> bool:
        candidate = token or self.token
        if candidate is None:
            return False
        released = bool(self._redis.eval(_RELEASE_SCRIPT, 1, self.key, candidate))
        if released and (token is None or token == self.token):
            self.token = None
        return released


def acquire_system_lock(redis: Any, system_id: UUID | str, ttl_seconds: int) -> RedisLock | None:
    lock = RedisLock(redis, system_ga_lock_key(system_id), ttl_seconds)
    return lock if lock.acquire() is not None else None


def release_system_lock(redis: Any, system_id: UUID | str, token: str | None) -> bool:
    if not token:
        return False
    return RedisLock(redis, system_ga_lock_key(system_id), 1).release(token)
