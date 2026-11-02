from __future__ import annotations

import hashlib

import pytest

from app.infrastructure.storage.base import StorageError, sha256_bytes, sha256_stream
from app.infrastructure.storage.local import LocalArtifactStorage


def test_open_nonexistent_key_is_not_found(tmp_path):
    storage = LocalArtifactStorage(tmp_path)
    with pytest.raises(StorageError):
        storage.open("nope.py")


def test_delete_is_idempotent(tmp_path):
    storage = LocalArtifactStorage(tmp_path)
    key, _ = storage.write(b"demo")
    storage.delete(key)
    storage.delete(key)  # missing_ok, no error
    assert not storage.exists(key)
    assert not any(tmp_path.iterdir())


def test_local_storage_roundtrip_and_deduplication(tmp_path):
    storage = LocalArtifactStorage(tmp_path)
    data = b"import numpy as np\ndef dynamics(t, x, u): ...\n"
    key, created = storage.write(data)
    key2, created2 = storage.write(data)

    assert created is True
    assert created2 is False
    assert key == key2
    assert storage.exists(key)
    assert storage.open(key) == data

    raw_path = hashlib.sha256(data).hexdigest() + ".py"
    assert (tmp_path / raw_path).read_bytes() == data


def test_key_must_be_single_path_component(tmp_path):
    storage = LocalArtifactStorage(tmp_path)
    with pytest.raises(StorageError):
        storage._blob_path("../evil.py")
    with pytest.raises(StorageError):
        storage._blob_path("sub/dir/key.py")
    with pytest.raises(StorageError):
        storage._blob_path(".hidden.py")


def test_writable_flags_broken_dir(tmp_path):
    working = LocalArtifactStorage(tmp_path)
    assert working.writable() is True

    read_only = LocalArtifactStorage(tmp_path / "nested" / "nope")
    (tmp_path / "nested").mkdir(parents=True)
    (tmp_path / "nested" / "nope").write_text("not a dir")
    assert read_only.writable() is False


def test_sha256_helpers():
    digest, size = sha256_bytes(b"abc")
    assert size == 3
    assert digest == hashlib.sha256(b"abc").hexdigest()

    import io

    digest, size = sha256_stream(io.BytesIO(b"hello world"))
    assert size == 11
    assert digest == hashlib.sha256(b"hello world").hexdigest()


def test_local_storage_survives_restart(tmp_path):
    storage = LocalArtifactStorage(tmp_path)
    key, _ = storage.write(b"persist me")
    storage2 = LocalArtifactStorage(tmp_path)
    assert storage2.exists(key)
    assert storage2.open(key) == b"persist me"
