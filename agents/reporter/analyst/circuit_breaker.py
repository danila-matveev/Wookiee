# agents/reporter/analyst/circuit_breaker.py
"""Circuit breaker for LLM calls — stops retrying after N failures."""
from __future__ import annotations

import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Stopped — too many failures
    HALF_OPEN = "half_open" # Testing with single request


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_sec: float = 3600.0):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.cooldown_sec:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one try
        return True

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self._last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
