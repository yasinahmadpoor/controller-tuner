from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.infrastructure.storage.base import ArtifactStorage, StorageError


class LocalArtifactStorage(ArtifactStorage):
    """Content-addressed storage under a single directory.

    Blob file names are ``<sha256>.bin``; the caller is responsible for adding a
    rich extension (e.g. ``.py``) if it needs one — the common engine contract
    only ever re-opens the blob by exact key.
    """

    def __init__(self, root_dir: Path | str):
        self.root_dir = Path(root_dir).expanduser().resolve()

    def _blob_path(self, key: str) -> Path:
        _root = self.root_dir
        if Path(key).name != key or "/" in key or "\\" in key or key.startswith("."):
            raise StorageError(f"Unsafe artifact key: {key!r}")
        return _root / key

    def _ensure_root(self) -> None:
        try:
            self.root_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError(f"Cannot create artifact dir {self.root_dir}: {exc}") from exc

    def write(self, data: bytes) -> tuple[str, bool]:
        import hashlib

        key = hashlib.sha256(data).hexdigest() + ".py"
        path = self._blob_path(key)
        self._ensure_root()
        if path.exists():
            return key, False
        try:
            with tempfile.NamedTemporaryFile(dir=self.root_dir, delete=False, suffix=".tmp") as tmp:
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = Path(tmp.name)
            tmp_path.rename(path)
        except OSError as exc:
            raise StorageError(f"Cannot write artifact {key}: {exc}") from exc
        return key, True

    def open(self, key: str) -> bytes:
        path = self._blob_path(key)
        try:
            return path.read_bytes()
        except (OSError, FileNotFoundError) as exc:
            raise StorageError(f"Cannot read artifact {key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        return self._blob_path(key).exists()

    def delete(self, key: str) -> None:
        path = self._blob_path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"Cannot delete artifact {key}: {exc}") from exc

    def writable(self) -> bool:
        try:
            with tempfile.TemporaryFile(dir=self.root_dir) as tmp:
                tmp.write(b"healthcheck")
            return True
        except OSError:
            try:
                self._ensure_root()
            except StorageError:
                return False
            try:
                with tempfile.TemporaryFile(dir=self.root_dir) as tmp:
                    tmp.write(b"healthcheck")
                return True
            except OSError:
                return False
