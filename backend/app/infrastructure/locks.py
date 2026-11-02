from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from redis import Redis

LOCK_PREFIX = "lock"
DEFAULT_LOCK_TTL_SECONDS = 120.0


def lock_key(kind: str, identifier: str) -> str:
    return f"{LOCK_PREFIX}:{kind}:{identifier}"


def try_lock(
    redis_client: Redis,
    key: str,
    ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
    token: str | None = None,
) -> str | None:
    """Acquire a Redis lock with a random owner token. Returns the token or None.

    Lua atomic SET NX with TTL avoids the classic set-then-expire race.
    """
    owner = token or uuid.uuid4().hex
    acquired = redis_client.set(key, owner, nx=True, ex=max(1, round(ttl_seconds)))
    if acquired:
        return owner
    return None


def release_lock(redis_client: Redis, key: str, token: str) -> None:
    """Release the lock only if we still own it (token-safety)."""
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    redis_client.eval(script, 1, key, token)


def lock_info(redis_client: Redis, key: str) -> dict[str, Any]:
    """Best-effort introspection helper: owner ttl + remaining ttl."""
    owner = redis_client.get(key)
    ttl = redis_client.ttl(key)
    return {"held": owner is not None, "ttl": ttl if ttl is not None else None}


@contextmanager
def redis_lock(
    redis_client: Redis,
    key: str,
    ttl_seconds: float = DEFAULT_LOCK_TTL_SECONDS,
) -> Iterator[str | None]:
    """Yield the lock token (or None if not acquired). Caller must handle None meaning contention."""
    token = try_lock(redis_client, key, ttl_seconds=ttl_seconds)
    try:
        yield token
    finally:
        if token is not None:
            release_lock(redis_client, key, token)
