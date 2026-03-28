# tests/reporter/test_circuit_breaker.py
"""Tests for CircuitBreaker state machine."""
import time
from unittest.mock import patch

from agents.reporter.analyst.circuit_breaker import CircuitBreaker, CircuitState


def test_initial_state_closed():
    cb = CircuitBreaker(failure_threshold=3, cooldown_sec=60)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=60)
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute


def test_half_open_after_cooldown():
    cb = CircuitBreaker(failure_threshold=1, cooldown_sec=0.1)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    assert cb.can_execute  # transitions to HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN


def test_success_resets_to_closed():
    cb = CircuitBreaker(failure_threshold=2, cooldown_sec=0.1)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    time.sleep(0.15)
    _ = cb.can_execute  # HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


def test_failure_in_half_open_reopens():
    cb = CircuitBreaker(failure_threshold=1, cooldown_sec=0.1)
    cb.record_failure()
    time.sleep(0.15)
    _ = cb.can_execute  # HALF_OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
