"""Metadata / control / audit helpers (the operational spine, ADR-0005).

Defines the audit record shapes and a pluggable ``MetadataStore`` so pipelines
write batch/file/DQ audit and read/advance watermarks without caring where the
store lives. Phase 2 ships an in-memory store (tests) and a JSONL store (local
dev). Phase 4 adds a BigQuery-backed store implementing the same interface.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scb_common.context import utcnow


@dataclass
class BatchAudit:
    batch_id: str
    pipeline: str
    source: str
    destination: str
    status: str = "running"  # running | success | failed
    rows_read: int = 0
    rows_written: int = 0
    rows_rejected: int = 0
    started_at: str = field(default_factory=lambda: utcnow().isoformat())
    ended_at: str | None = None
    duration_s: float | None = None
    error: str | None = None


@dataclass
class FileAudit:
    batch_id: str
    source: str
    filename: str
    checksum: str
    size_bytes: int
    status: str = "landed"  # landed | processed | skipped_duplicate | failed
    seen_at: str = field(default_factory=lambda: utcnow().isoformat())


@dataclass
class DQResultRecord:
    batch_id: str
    entity: str
    rule: str
    severity: str
    passed: int
    failed: int
    threshold: float
    breached: bool
    sample_keys: list[Any] = field(default_factory=list)
    at: str = field(default_factory=lambda: utcnow().isoformat())


class MetadataStore(ABC):
    """Interface every backend (in-memory, JSONL, BigQuery) implements."""

    @abstractmethod
    def write_batch(self, audit: BatchAudit) -> None: ...

    @abstractmethod
    def write_file(self, audit: FileAudit) -> None: ...

    @abstractmethod
    def write_dq(self, records: list[DQResultRecord]) -> None: ...

    @abstractmethod
    def get_watermark(self, entity: str) -> str | None: ...

    @abstractmethod
    def set_watermark(self, entity: str, value: str) -> None: ...

    @abstractmethod
    def is_file_seen(self, source: str, checksum: str) -> bool: ...


class InMemoryMetadataStore(MetadataStore):
    """Non-persistent store for unit tests."""

    def __init__(self) -> None:
        self.batches: list[BatchAudit] = []
        self.files: list[FileAudit] = []
        self.dq: list[DQResultRecord] = []
        self._watermarks: dict[str, str] = {}
        self._checksums: set[tuple[str, str]] = set()

    def write_batch(self, audit: BatchAudit) -> None:
        self.batches.append(audit)

    def write_file(self, audit: FileAudit) -> None:
        self.files.append(audit)
        self._checksums.add((audit.source, audit.checksum))

    def write_dq(self, records: list[DQResultRecord]) -> None:
        self.dq.extend(records)

    def get_watermark(self, entity: str) -> str | None:
        return self._watermarks.get(entity)

    def set_watermark(self, entity: str, value: str) -> None:
        self._watermarks[entity] = value

    def is_file_seen(self, source: str, checksum: str) -> bool:
        return (source, checksum) in self._checksums


class JsonlMetadataStore(MetadataStore):
    """Append-only JSONL store for local development. Thread-safe for a single process.

    One file per record type under ``base_dir``, plus a small JSON watermark file.
    Good enough to make local runs observable and idempotent before BigQuery exists.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._wm_path = self.base / "watermarks.json"
        self._seen_path = self.base / "file_checksums.jsonl"

    def _append(self, name: str, obj: dict[str, Any]) -> None:
        with self._lock, (self.base / f"{name}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, default=str) + "\n")

    def write_batch(self, audit: BatchAudit) -> None:
        self._append("batch_audit", asdict(audit))

    def write_file(self, audit: FileAudit) -> None:
        self._append("file_audit", asdict(audit))
        self._append("file_checksums", {"source": audit.source, "checksum": audit.checksum})

    def write_dq(self, records: list[DQResultRecord]) -> None:
        for r in records:
            self._append("dq_results", asdict(r))

    def get_watermark(self, entity: str) -> str | None:
        if not self._wm_path.is_file():
            return None
        data = json.loads(self._wm_path.read_text(encoding="utf-8"))
        return data.get(entity)

    def set_watermark(self, entity: str, value: str) -> None:
        with self._lock:
            data: dict[str, str] = {}
            if self._wm_path.is_file():
                data = json.loads(self._wm_path.read_text(encoding="utf-8"))
            data[entity] = value
            self._wm_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_file_seen(self, source: str, checksum: str) -> bool:
        if not self._seen_path.is_file():
            return False
        for line in self._seen_path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec.get("source") == source and rec.get("checksum") == checksum:
                return True
        return False


def finalize(audit: BatchAudit, *, status: str, error: str | None = None) -> BatchAudit:
    """Stamp end time/duration/status on a batch audit record."""
    end = utcnow()
    audit.ended_at = end.isoformat()
    started = datetime.fromisoformat(audit.started_at)
    audit.duration_s = round((end - started).total_seconds(), 3)
    audit.status = status
    audit.error = error
    return audit
