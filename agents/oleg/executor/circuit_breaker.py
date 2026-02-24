"""
Circuit Breaker — prevents cascading failures in tool/LLM calls.

States:
- CLOSED: normal operation, calls pass through
- OPEN: calls blocked, returns error immediately
- HALF_OPEN: allow one test call after cooldown

Transition: CLOSED → (N failures) → OPEN → (cooldown) → HALF_OPEN → (success) → CLOSED
                                                                     (failure) → OPEN
"""
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for tool and LLM calls."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        cooldown_sec: float = 300.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.cooldown_sec:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    f"CircuitBreaker[{self.name}]: OPEN → HALF_OPEN "
                    f"(cooldown {self.cooldown_sec}s elapsed)"
                )
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request is allowed through the breaker."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # allow one test call
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call. Resets failure count."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"CircuitBreaker[{self.name}]: HALF_OPEN → CLOSED (success)")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def record_failure(self) -> None:
        """Record a failed call. May trip the breaker."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(
                f"CircuitBreaker[{self.name}]: HALF_OPEN → OPEN (test call failed)"
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"CircuitBreaker[{self.name}]: CLOSED → OPEN "
                f"({self._failure_count} consecutive failures, "
                f"cooldown {self.cooldown_sec}s)"
            )

    def reset(self) -> None:
        """Force reset to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None

    def status(self) -> dict:
        """Return current breaker status for diagnostics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "cooldown_sec": self.cooldown_sec,
            "last_failure": self._last_failure_time,
        }
