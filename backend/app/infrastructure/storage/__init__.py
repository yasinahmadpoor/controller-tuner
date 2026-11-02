from app.infrastructure.storage.base import (
    ArtifactStorage,
    StorageError,
    sha256_bytes,
    sha256_stream,
)
from app.infrastructure.storage.local import LocalArtifactStorage


def create_storage(
    backend: str, *, local_dir: str | None = None, bucket: str | None = None
) -> ArtifactStorage:
    if backend == "local":
        if local_dir is None:
            raise ValueError("local backend requires local_dir")
        return LocalArtifactStorage(local_dir)
    if backend == "s3":
        if bucket is None:
            raise ValueError("s3 backend requires bucket")
        from app.infrastructure.storage.s3 import S3ArtifactStorage

        return S3ArtifactStorage(bucket)
    raise ValueError(f"Unknown artifact backend: {backend!r}")


__all__ = [
    "ArtifactStorage",
    "LocalArtifactStorage",
    "StorageError",
    "create_storage",
    "sha256_bytes",
    "sha256_stream",
]
