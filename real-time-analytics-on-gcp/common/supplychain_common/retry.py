"""Exponential backoff with jitter for retrying transient failures.

Used anywhere a component talks to a broker/service that can be
momentarily unavailable (Kafka leader election in progress, Pub/Sub
throttling, a flaky carrier API during enrichment). Not used for schema
validation failures — those are permanent (poison messages) and retrying
them just wastes time before they land on the DLQ anyway.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetriesExhausted(Exception):
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"gave up after {attempts} attempts: {last_error}")


def call_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 5,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Calls `fn()`, retrying on exceptions in `retry_on` with exponential
    backoff + full jitter (delay = random(0, min(max_delay, base * 2^attempt))).

    Full jitter avoids every retrying client waking up in lockstep and
    re-hammering a broker that's already struggling — a fixed or
    non-jittered exponential curve doesn't have that property.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except retry_on as exc:
            if attempt >= max_attempts:
                raise RetriesExhausted(attempt, exc) from exc
            delay = random.uniform(0, min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1))))
            logger.warning(
                "attempt %d/%d failed (%s); retrying in %.2fs",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)
