import pytest

from scb_common.retry import retry


def test_succeeds_after_transient_failures():
    calls = {"n": 0}

    @retry(attempts=3, base_delay=0, jitter=False, sleep=lambda _: None)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_reraises_after_exhausting_attempts():
    calls = {"n": 0}

    @retry(attempts=2, base_delay=0, jitter=False, sleep=lambda _: None, exceptions=(TimeoutError,))
    def always_fail():
        calls["n"] += 1
        raise TimeoutError("nope")

    with pytest.raises(TimeoutError):
        always_fail()
    assert calls["n"] == 2


def test_non_listed_exception_not_retried():
    calls = {"n": 0}

    @retry(attempts=3, base_delay=0, sleep=lambda _: None, exceptions=(ConnectionError,))
    def raises_value():
        calls["n"] += 1
        raise ValueError("data error, do not retry")

    with pytest.raises(ValueError):
        raises_value()
    assert calls["n"] == 1


def test_on_retry_callback_invoked():
    seen = []

    @retry(
        attempts=3,
        base_delay=0,
        jitter=False,
        sleep=lambda _: None,
        on_retry=lambda attempt, exc, delay: seen.append(attempt),
    )
    def flaky():
        if len(seen) < 2:
            raise ConnectionError()
        return 1

    assert flaky() == 1
    assert seen == [1, 2]
