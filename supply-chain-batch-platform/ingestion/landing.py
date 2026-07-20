"""Landing/archive storage abstraction + checksums.

A ``LandingStore`` hides *where* files live so the extractor is identical locally
(filesystem) and in the cloud (GCS). Phase 5 ships the local implementation and a
thin GCS stub (lazy import) documenting the enterprise swap.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Protocol


class LandingStore(Protocol):
    def exists(self, path: str) -> bool: ...
    def list(self, pattern: str) -> list[str]: ...
    def read_bytes(self, path: str) -> bytes: ...
    def checksum(self, path: str) -> str: ...
    def archive(self, path: str, archive_root: str, dataset: str) -> str: ...


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalLandingStore:
    """Filesystem-backed store (local dev, $0)."""

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def list(self, pattern: str) -> list[str]:
        # pattern is a glob relative to cwd or absolute
        base = Path(pattern)
        if base.exists():
            return [str(base)]
        parent = base.parent
        return sorted(str(p) for p in parent.glob(base.name)) if parent.exists() else []

    def read_bytes(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def checksum(self, path: str) -> str:
        return sha256_bytes(self.read_bytes(path))

    def archive(self, path: str, archive_root: str, dataset: str) -> str:
        """Copy (not move) the source file into the archive, preserving demo re-runs.

        Enterprise typically *moves* files out of landing after success; we copy so
        the same run can be replayed to demonstrate checksum-based dedup.
        """
        src = Path(path)
        dest_dir = Path(archive_root) / dataset
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        return str(dest)


class GcsLandingStore:
    """GCS-backed store (enterprise). Lazy-imports google-cloud-storage.

    Not exercised in local runs; documented so the extractor code is cloud-ready
    without change (just swap the store).
    """

    def __init__(self, project: str | None = None) -> None:
        from google.cloud import storage  # lazy

        self._client = storage.Client(project=project)

    @staticmethod
    def _split(uri: str) -> tuple[str, str]:
        assert uri.startswith("gs://"), uri
        bucket, _, key = uri[5:].partition("/")
        return bucket, key

    def exists(self, path: str) -> bool:
        bucket, key = self._split(path)
        return self._client.bucket(bucket).blob(key).exists()

    def list(self, pattern: str) -> list[str]:
        bucket, prefix = self._split(pattern.rstrip("*"))
        return [f"gs://{bucket}/{b.name}" for b in self._client.list_blobs(bucket, prefix=prefix)]

    def read_bytes(self, path: str) -> bytes:
        bucket, key = self._split(path)
        return self._client.bucket(bucket).blob(key).download_as_bytes()

    def checksum(self, path: str) -> str:
        return sha256_bytes(self.read_bytes(path))

    def archive(self, path: str, archive_root: str, dataset: str) -> str:
        bucket, key = self._split(path)
        dest = f"{archive_root.rstrip('/')}/{dataset}/{Path(key).name}"
        db, dk = self._split(dest)
        src_blob = self._client.bucket(bucket).blob(key)
        self._client.bucket(bucket).copy_blob(src_blob, self._client.bucket(db), dk)
        return dest
