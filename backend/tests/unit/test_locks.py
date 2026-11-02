from __future__ import annotations

from typing import Any

from app.infrastructure.locks import (
    RedisLock,
    acquire_system_lock,
    release_system_lock,
    system_ga_lock_key,
)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> Any:
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


def test_acquire_release_and_contention():
    redis = FakeRedis()
    lock = RedisLock(redis, "lock:system:1:ga", 30)

    token = lock.acquire()
    assert token is not None
    assert redis.store["lock:system:1:ga"] == token

    contender = RedisLock(redis, "lock:system:1:ga", 30)
    assert contender.acquire() is None

    assert lock.release() is True
    assert "lock:system:1:ga" not in redis.store
    assert contender.acquire() is not None


def test_token_safety_prevents_releasing_someone_elses_lock():
    redis = FakeRedis()
    first = RedisLock(redis, "lock", 30)
    first.acquire()
    stale_token = first.token

    first.release()
    second = RedisLock(redis, "lock", 30)
    second.acquire()

    assert first.release(stale_token) is False
    assert "lock" in redis.store
    assert second.release() is True


def test_system_lock_helpers_use_expected_key():
    redis = FakeRedis()
    lock = acquire_system_lock(redis, "system-1", 10)

    assert lock is not None
    assert system_ga_lock_key("system-1") == "lock:system:system-1:ga"
    assert release_system_lock(redis, "system-1", lock.token) is True
    assert release_system_lock(redis, "system-1", lock.token) is False
