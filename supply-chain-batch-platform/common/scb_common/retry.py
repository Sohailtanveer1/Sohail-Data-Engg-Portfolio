"""Retry with exponential backoff for transient I/O (SFTP, REST, JDBC).

Only retry *transient* failures (network, throttling). Never retry data errors —
a bad file is still bad on the third attempt (see errors.py). Pair with
idempotent writes (ADR-0007) so a retried run is safe.

    @retry(attempts=5, base_delay=1.0, exceptions=(ConnectionError, TimeoutError))
    def fetch_page(url): ...
"""

from __future__ import annotations

import functools
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: retry a callable on ``exceptions`` with exponential backoff.

    ``on_retry(attempt, exc, delay)`` is called before each sleep (for logging).
    ``sleep`` is injectable so tests run instantly.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            delay = base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == attempts:
                        break
                    wait = min(delay, max_delay)
                    if jitter:
                        wait = wait * (0.5 + random.random() / 2)
                    if on_retry is not None:
                        on_retry(attempt, exc, wait)
                    sleep(wait)
                    delay *= backoff
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
