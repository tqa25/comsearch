import logging
import threading
import time

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Adaptive pacing based on API responses.

    Thread-safe rate limiter that adjusts delay based on success/error rates.
    """

    def __init__(
        self,
        initial_delay: float = 3.0,
        min_delay: float = 1.0,
        max_delay: float = 120.0,
    ):
        self.current_delay = initial_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._lock = threading.Lock()
        self._last_call_time: float = 0

    def wait(self):
        """Wait before next API call."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self.current_delay:
                wait_time = self.current_delay - elapsed
                logger.debug(f"Rate limiter wait: {wait_time:.1f}s")
                time.sleep(wait_time)
            self._last_call_time = time.time()

    def report_success(self):
        """Decrease delay on success (min 1s)."""
        with self._lock:
            old_delay = self.current_delay
            self.current_delay = max(self.min_delay, self.current_delay * 0.9)
            if self.current_delay != old_delay:
                logger.debug(
                    f"Rate limiter: delay {old_delay:.1f}s → {self.current_delay:.1f}s"
                )

    def report_error(self, status_code: int):
        """Increase delay on error."""
        with self._lock:
            old_delay = self.current_delay
            if status_code == 429:
                self.current_delay = min(self.max_delay, self.current_delay * 2.0)
            else:
                self.current_delay = min(self.max_delay, self.current_delay * 1.5)
            if self.current_delay != old_delay:
                logger.debug(
                    f"Rate limiter (error {status_code}): "
                    f"delay {old_delay:.1f}s → {self.current_delay:.1f}s"
                )
