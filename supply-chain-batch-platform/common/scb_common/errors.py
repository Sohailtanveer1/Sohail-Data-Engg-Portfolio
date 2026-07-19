"""Typed exceptions for the platform.

Typed errors let callers (and Airflow) distinguish *data* problems (fail the
batch, quarantine, alert the data team) from *config/infra* problems (retry,
alert the platform team). Never raise bare ``Exception`` in pipeline code.
"""

from __future__ import annotations


class ScbError(Exception):
    """Base class for all platform errors."""


class ConfigError(ScbError):
    """A configuration value is missing, malformed, or invalid."""


class SchemaValidationError(ScbError):
    """Incoming data does not satisfy its registered schema contract."""

    def __init__(self, message: str, *, missing: list[str] | None = None,
                 unexpected: list[str] | None = None,
                 type_errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing = missing or []
        self.unexpected = unexpected or []
        self.type_errors = type_errors or []


class DataQualityError(ScbError):
    """One or more ``error``-severity data-quality rules failed beyond threshold."""

    def __init__(self, message: str, *, failed_rules: list[str] | None = None) -> None:
        super().__init__(message)
        self.failed_rules = failed_rules or []


class RetryableError(ScbError):
    """A transient failure (network, throttling) that is safe to retry."""
