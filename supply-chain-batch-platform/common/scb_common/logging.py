"""Structured JSON logging.

Every component logs one JSON object per line so Cloud Logging can index the
fields and Cloud Monitoring can build metrics/alerts on them. The platform's log
envelope (from the design docs) is:

    pipeline, batch_id, source, destination,
    rows_read, rows_written, rows_rejected,
    duration_s, status, error

Usage:
    log = get_logger("silver.material", ctx=batch_context)
    log.info("read_complete", rows_read=12000)
    log.metrics(rows_read=12000, rows_written=11940, rows_rejected=60,
                duration_s=8.2, status="success")
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from scb_common.context import BatchContext

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    """Render a LogRecord (plus any ``record.fields`` dict) as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class _StdoutHandler(logging.Handler):
    """Handler that resolves ``sys.stdout`` at emit time.

    Binding the stream at construction (as ``logging.StreamHandler`` does) breaks
    when ``sys.stdout`` is later replaced — e.g. pytest's ``capsys``, or a harness
    that redirects output. Resolving lazily keeps one configured handler correct
    across such swaps.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
        except Exception:  # pragma: no cover - stdlib logging contract
            self.handleError(record)


def _configure_root(level: int) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = _StdoutHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


class StructuredLogger:
    """Thin wrapper that always emits the batch envelope + arbitrary fields."""

    def __init__(
        self, name: str, ctx: BatchContext | None = None, base_fields: dict[str, Any] | None = None
    ) -> None:
        self._log = logging.getLogger(name)
        self._base: dict[str, Any] = {}
        if ctx is not None:
            self._base.update(ctx.log_fields())
        if base_fields:
            self._base.update(base_fields)

    def bind(self, **fields: Any) -> StructuredLogger:
        """Return a child logger with extra fields permanently attached."""
        child = StructuredLogger(self._log.name)
        child._base = {**self._base, **fields}
        return child

    def _emit(self, level: int, message: str, exc_info: bool = False, **fields: Any) -> None:
        self._log.log(level, message, extra={"fields": {**self._base, **fields}}, exc_info=exc_info)

    def debug(self, message: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit(logging.INFO, message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit(logging.WARNING, message, **fields)

    def error(self, message: str, exc_info: bool = False, **fields: Any) -> None:
        self._emit(logging.ERROR, message, exc_info=exc_info, **fields)

    def metrics(
        self,
        *,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        rows_rejected: int = 0,
        duration_s: float | None = None,
        error: str | None = None,
        **extra: Any,
    ) -> None:
        """Emit the canonical end-of-stage metrics line."""
        self._emit(
            logging.INFO if status == "success" else logging.ERROR,
            "pipeline_metrics",
            rows_read=rows_read,
            rows_written=rows_written,
            rows_rejected=rows_rejected,
            duration_s=round(duration_s, 3) if duration_s is not None else None,
            status=status,
            error=error,
            **extra,
        )


def get_logger(
    name: str, ctx: BatchContext | None = None, level: int = logging.INFO, **base_fields: Any
) -> StructuredLogger:
    """Return a configured structured logger.

    Root JSON handler is configured once on first call (idempotent).
    """
    _configure_root(level)
    return StructuredLogger(name, ctx=ctx, base_fields=base_fields or None)


def attach_handler(handler: logging.Handler, level: int = logging.INFO) -> None:
    """Attach an extra handler to the root logger (e.g. a Cloud Logging handler)."""
    _configure_root(level)
    logging.getLogger().addHandler(handler)


def enable_cloud_logging(level: int = logging.INFO) -> logging.Handler:
    """Ship structured logs to Cloud Logging.

    On GCP-managed runtimes (Composer/Dataproc) our JSON-to-stdout is already
    parsed into ``jsonPayload`` automatically — which is what the log-based metrics
    (Phase 9 `monitoring` module) filter on. This helper attaches an explicit
    StructuredLogHandler for non-managed contexts. Lazy import of the optional
    ``google-cloud-logging`` dependency.
    """
    from google.cloud.logging_v2.handlers import StructuredLogHandler

    handler = StructuredLogHandler()
    handler.setFormatter(_JsonFormatter())
    attach_handler(handler, level)
    return handler
