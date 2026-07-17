import unittest

from auth.rate_limit import LoginRateLimiter


class LoginRateLimiterTests(unittest.TestCase):
    def test_blocks_only_after_configured_failures(self) -> None:
        limiter = LoginRateLimiter(attempts=2, window_seconds=60)

        limiter.record_failure("client", now=10)
        self.assertEqual(limiter.retry_after("client", now=11), 0)
        limiter.record_failure("client", now=12)
        self.assertGreater(limiter.retry_after("client", now=13), 0)

        limiter.record_success("client")
        self.assertEqual(limiter.retry_after("client", now=13), 0)

    def test_old_failures_expire(self) -> None:
        limiter = LoginRateLimiter(attempts=1, window_seconds=5)
        limiter.record_failure("client", now=1)

        self.assertEqual(limiter.retry_after("client", now=7), 0)


if __name__ == "__main__":
    unittest.main()
