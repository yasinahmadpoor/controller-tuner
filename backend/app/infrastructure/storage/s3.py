from __future__ import annotations

from app.infrastructure.storage.base import ArtifactStorage, StorageError


class S3ArtifactStorage(ArtifactStorage):
    """S3/MinIO-backed artifact storage.

    Deferred until the MVP moves off a single shared local volume; the shape
    matches ``LocalArtifactStorage`` so Phase 2+ services only care about
    the abstract interface, not the concrete backend.
    """

    def __init__(self, bucket: str, prefix: str = "artifacts/"):
        raise NotImplementedError("S3 artifact backend planned for later phase")

    def write(self, data: bytes) -> tuple[str, bool]:  # pragma: no cover
        raise StorageError("S3 backend not implemented")

    def open(self, key: str) -> bytes:  # pragma: no cover
        raise StorageError("S3 backend not implemented")

    def exists(self, key: str) -> bool:  # pragma: no cover
        raise StorageError("S3 backend not implemented")

    def delete(self, key: str) -> None:  # pragma: no cover
        raise StorageError("S3 backend not implemented")

    def writable(self) -> bool:  # pragma: no cover
        return False
