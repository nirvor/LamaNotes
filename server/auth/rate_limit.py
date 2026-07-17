import threading
import time
from collections import defaultdict, deque


class LoginRateLimiter:
    def __init__(self, attempts: int = 8, window_seconds: int = 300) -> None:
        self.attempts = max(1, attempts)
        self.window_seconds = max(1, window_seconds)
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, key: str, now: float | None = None) -> int:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            failures = self._prune(key, timestamp)
            if len(failures) < self.attempts:
                return 0
            return max(1, int(self.window_seconds - (timestamp - failures[0])))

    def record_failure(self, key: str, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            failures = self._prune(key, timestamp)
            failures.append(timestamp)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        cutoff = now - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
            failures = self._failures[key]
        return failures
