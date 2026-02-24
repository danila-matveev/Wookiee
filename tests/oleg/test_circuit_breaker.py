"""Tests for CircuitBreaker."""
import time
from agents.oleg_v2.executor.circuit_breaker import CircuitBreaker


def test_initial_state_closed():
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=1.0)
    assert cb.allow_request() is True
    status = cb.status()
    assert status["state"] == "closed"


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=1.0)
    cb.record_failure()
    cb.record_failure()
    assert cb.allow_request() is True  # 2 failures, threshold is 3
    cb.record_failure()
    assert cb.allow_request() is False  # 3 failures → OPEN
    assert cb.status()["state"] == "open"


def test_success_resets_failure_count():
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=1.0)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()  # Reset
    cb.record_failure()
    cb.record_failure()
    assert cb.allow_request() is True  # Only 2 failures after reset


def test_half_open_after_cooldown():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.allow_request() is False  # OPEN

    time.sleep(0.15)  # Wait for cooldown
    assert cb.allow_request() is True  # HALF_OPEN → allows one request


def test_closes_after_success_in_half_open():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=0.1)
    cb.record_failure()
    cb.record_failure()

    time.sleep(0.15)
    assert cb.allow_request() is True  # HALF_OPEN
    cb.record_success()
    assert cb.status()["state"] == "closed"
    assert cb.allow_request() is True
