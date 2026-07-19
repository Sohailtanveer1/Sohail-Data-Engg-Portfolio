import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from supplychain_common.retry import RetriesExhausted, call_with_backoff  # noqa: E402


def test_succeeds_first_try_no_retry():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    assert call_with_backoff(fn, max_attempts=5, base_delay_seconds=0) == "ok"
    assert len(calls) == 1


def test_succeeds_after_transient_failures():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    result = call_with_backoff(fn, max_attempts=5, base_delay_seconds=0, retry_on=(ConnectionError,))
    assert result == "ok"
    assert calls["n"] == 3


def test_gives_up_after_max_attempts():
    def fn():
        raise ConnectionError("always fails")

    with pytest.raises(RetriesExhausted) as exc_info:
        call_with_backoff(fn, max_attempts=3, base_delay_seconds=0, retry_on=(ConnectionError,))
    assert exc_info.value.attempts == 3


def test_does_not_retry_unlisted_exception():
    def fn():
        raise ValueError("permanent, not in retry_on")

    with pytest.raises(ValueError):
        call_with_backoff(fn, max_attempts=5, base_delay_seconds=0, retry_on=(ConnectionError,))
