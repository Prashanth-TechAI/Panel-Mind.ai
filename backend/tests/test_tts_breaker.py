"""The breaker exists purely to protect the latency budget.

A provider that is out of credits still burns ~600ms rejecting each request,
and paying that on every utterance would wreck the interview. These tests pin
the behaviour that keeps the cost of a dead provider at zero.
"""

from __future__ import annotations

from app.providers.tts import CircuitBreaker


class FakeClock:
    def __init__(self, start_ms: float = 0.0) -> None:
        self._now = start_ms

    def __call__(self) -> float:
        return self._now

    def advance(self, ms: float) -> None:
        self._now += ms


class TestCircuitBreaker:
    def test_starts_closed(self):
        breaker = CircuitBreaker(now=FakeClock())
        assert breaker.is_open("elevenlabs") is False

    def test_trips_immediately_on_exhausted_credits(self):
        breaker = CircuitBreaker(now=FakeClock())

        tripped = breaker.record_failure("elevenlabs", "quota", "0 credits remaining")

        assert tripped is True
        assert breaker.is_open("elevenlabs") is True
        assert breaker.reason_for("elevenlabs") == "0 credits remaining"

    def test_keeps_the_quota_cooldown_for_five_minutes_then_retries(self):
        clock = FakeClock()
        breaker = CircuitBreaker(now=clock)

        breaker.record_failure("elevenlabs", "quota", "0 credits")

        clock.advance(4 * 60_000)
        assert breaker.is_open("elevenlabs") is True, "should still be open at 4 minutes"

        clock.advance(61_000)
        assert breaker.is_open("elevenlabs") is False, "should retry after 5 minutes"

    def test_holds_a_bad_key_open_longer_than_a_bad_quota(self):
        clock = FakeClock()
        breaker = CircuitBreaker(now=clock)

        breaker.record_failure("elevenlabs", "auth", "401 unauthorized")

        clock.advance(6 * 60_000)
        assert breaker.is_open("elevenlabs") is True, "a rejected key does not fix itself"

        clock.advance(5 * 60_000)
        assert breaker.is_open("elevenlabs") is False

    def test_tolerates_isolated_blips_and_only_trips_on_a_run_of_them(self):
        breaker = CircuitBreaker(now=FakeClock())

        assert breaker.record_failure("elevenlabs", "transient", "ECONNRESET") is False
        assert breaker.is_open("elevenlabs") is False

        assert breaker.record_failure("elevenlabs", "transient", "ECONNRESET") is False
        assert breaker.is_open("elevenlabs") is False

        assert breaker.record_failure("elevenlabs", "transient", "ECONNRESET") is True
        assert breaker.is_open("elevenlabs") is True

    def test_forgets_the_transient_run_once_a_call_succeeds(self):
        breaker = CircuitBreaker(now=FakeClock())

        breaker.record_failure("elevenlabs", "transient", "blip")
        breaker.record_failure("elevenlabs", "transient", "blip")
        breaker.record_success("elevenlabs")

        # Counter reset: two more blips must not be enough to trip it.
        breaker.record_failure("elevenlabs", "transient", "blip")
        breaker.record_failure("elevenlabs", "transient", "blip")
        assert breaker.is_open("elevenlabs") is False

    def test_tracks_providers_independently_so_one_failure_cannot_mute_the_board(self):
        breaker = CircuitBreaker(now=FakeClock())

        breaker.record_failure("elevenlabs", "quota", "0 credits")

        assert breaker.is_open("elevenlabs") is True
        assert breaker.is_open("deepgram") is False, "the fallback must stay available"

    def test_clears_the_breaker_on_a_success_after_the_cooldown(self):
        clock = FakeClock()
        breaker = CircuitBreaker(now=clock)

        breaker.record_failure("elevenlabs", "quota", "0 credits")
        clock.advance(6 * 60_000)
        breaker.record_success("elevenlabs")

        assert breaker.is_open("elevenlabs") is False
        assert breaker.reason_for("elevenlabs") is None
