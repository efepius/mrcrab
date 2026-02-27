import time
from collections import defaultdict


class RateLimiter:
    """
    Token-bucket rate limiter per user.
    Default: 20 messages per 60 seconds per user.
    """

    def __init__(self, max_calls: int = 20, period_seconds: float = 60.0):
        self.max_calls = max_calls
        self.period = period_seconds
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, user_key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.period
        bucket = self._buckets[user_key]

        # Remove timestamps outside the window
        self._buckets[user_key] = [t for t in bucket if t > cutoff]

        if len(self._buckets[user_key]) >= self.max_calls:
            return False

        self._buckets[user_key].append(now)
        return True

    def seconds_until_allowed(self, user_key: str) -> float:
        bucket = self._buckets.get(user_key, [])
        if not bucket or len(bucket) < self.max_calls:
            return 0.0
        oldest = min(bucket)
        wait = self.period - (time.monotonic() - oldest)
        return max(0.0, wait)
