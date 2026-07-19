"""BatchContext — the correlation object every pipeline run carries.

``batch_id`` is the single most important operational field in the platform: it
ties together logs, the ``batch_audit`` / ``file_audit`` / ``dq_results`` tables,
and the physical output partitions of one run. Generate it once at the start of a
run and thread it through everything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC now, timezone-aware. Always use this instead of ``datetime.now()``."""
    return datetime.now(timezone.utc)


def new_batch_id(pipeline: str, at: datetime | None = None) -> str:
    """A sortable, human-readable, unique batch id: ``<pipeline>-<utcts>-<short>``.

    Example: ``scb_sap_daily-20260719T183000Z-9f3a1c``. Sortable by time, unique
    per run, and self-describing in logs and GCS paths.
    """
    at = at or utcnow()
    stamp = at.strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:6]
    return f"{pipeline}-{stamp}-{short}"


@dataclass
class BatchContext:
    """Immutable-ish run context passed through a pipeline execution."""

    pipeline: str
    source: str
    destination: str = ""
    env: str = "local"
    batch_id: str = ""
    started_at: datetime = field(default_factory=utcnow)
    extra: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.batch_id:
            self.batch_id = new_batch_id(self.pipeline, self.started_at)

    def log_fields(self) -> dict[str, object]:
        """The base envelope merged into every structured log line for this run."""
        return {
            "pipeline": self.pipeline,
            "batch_id": self.batch_id,
            "source": self.source,
            "destination": self.destination,
            "env": self.env,
            **self.extra,
        }
