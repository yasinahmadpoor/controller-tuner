from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import BinaryIO

CHUNK_SIZE = 8192


def sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    """Hash a file-like object and return (hex digest, byte size)."""
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
        digest.update(chunk)
        size += len(chunk)
    stream.seek(0)
    return digest.hexdigest(), size


def sha256_bytes(data: bytes) -> tuple[str, int]:
    return hashlib.sha256(data).hexdigest(), len(data)


class StorageError(Exception):
    """Raised by a concrete backend I/O failure."""


class ArtifactStorage(ABC):
    """Content-addressed artifact storage. Identical bytes share one key."""

    @abstractmethod
    def write(self, data: bytes) -> tuple[str, bool]:
        """Persist bytes; returns (storage_key, created_now)."""

    @abstractmethod
    def open(self, key: str) -> bytes:
        """Read the artifact's bytes."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True when the artifact is present."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove the blob. Missing keys are not an error (idempotent cleanup)."""

    @abstractmethod
    def writable(self) -> bool:
        """Quick liveness check for readiness probes."""
