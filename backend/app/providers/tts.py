"""Speech synthesis with failover.

The board must never fall silent. ElevenLabs carries the distinctive Indian
voices that make the panel believable; Deepgram Aura is the understudy that
keeps the interview running when ElevenLabs is out of credits or down.

The circuit breaker is the part that matters for latency. A dead provider still
costs ~600ms to reject a request, and paying that on every single utterance
would blow the budget for the whole interview. After a provider-level failure
the breaker trips and subsequent calls skip straight to the fallback until the
cooldown expires.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from app.config import TtsProviderName, get_settings
from app.domain.board import MemberId, get_member
from app.logging_setup import timed

FailureKind = Literal["quota", "auth", "transient"]


class TtsError(Exception):
    def __init__(
        self,
        message: str,
        provider: TtsProviderName,
        kind: FailureKind,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.kind = kind
        self.status = status


# Cooldowns reflect how long the fault plausibly lasts. Exhausted credits do
# not reappear in twenty seconds; a network blip does.
COOLDOWN_MS: dict[FailureKind, int] = {
    "quota": 5 * 60_000,
    "auth": 10 * 60_000,
    "transient": 15_000,
}

# Consecutive transient failures tolerated before the breaker trips.
TRANSIENT_THRESHOLD = 3

SYNTH_TIMEOUT_S = 10.0


@dataclass(slots=True)
class _BreakerEntry:
    open_until_ms: float = 0.0
    consecutive_transient: int = 0
    last_reason: str = ""


def _default_clock() -> float:
    return time.monotonic() * 1000


@dataclass(slots=True)
class CircuitBreaker:
    """Injectable clock keeps this unit-testable without waiting minutes."""

    now: Callable[[], float] = _default_clock
    _entries: dict[TtsProviderName, _BreakerEntry] = field(default_factory=dict)

    def is_open(self, provider: TtsProviderName) -> bool:
        entry = self._entries.get(provider)
        return entry is not None and entry.open_until_ms > self.now()

    def reason_for(self, provider: TtsProviderName) -> str | None:
        entry = self._entries.get(provider)
        return entry.last_reason if entry else None

    def record_success(self, provider: TtsProviderName) -> None:
        self._entries.pop(provider, None)

    def record_failure(self, provider: TtsProviderName, kind: FailureKind, reason: str) -> bool:
        """Returns True if this failure tripped the breaker."""
        entry = self._entries.setdefault(provider, _BreakerEntry())
        entry.last_reason = reason

        if kind == "transient":
            entry.consecutive_transient += 1
            if entry.consecutive_transient < TRANSIENT_THRESHOLD:
                return False

        entry.open_until_ms = self.now() + COOLDOWN_MS[kind]
        entry.consecutive_transient = 0
        return True

    def reset(self) -> None:
        self._entries.clear()


breaker = CircuitBreaker()


@dataclass(slots=True)
class SynthesisResult:
    provider: TtsProviderName
    # Async byte stream. Consume it fully, then close the underlying response.
    chunks: AsyncIterator[bytes]
    content_type: str
    # Time to first byte — the number the latency budget actually cares about.
    ttfb_ms: int
    # Providers that were tried and rejected before this one answered.
    fell_back_from: list[TtsProviderName]
    _aclose: Callable[[], object]


def _classify(status: int, body: str) -> FailureKind:
    if "quota_exceeded" in body or status == 429:
        return "quota"
    if status in (401, 403):
        return "auth"
    return "transient"


async def _open_stream(
    client: httpx.AsyncClient,
    provider: TtsProviderName,
    request: httpx.Request,
) -> httpx.Response:
    response = await client.send(request, stream=True)

    if response.status_code >= 400:
        body = (await response.aread()).decode("utf-8", "replace")
        await response.aclose()
        raise TtsError(
            f"{provider} {response.status_code}: {body[:200]}",
            provider,
            _classify(response.status_code, body),
            response.status_code,
        )

    return response


async def _elevenlabs_request(
    client: httpx.AsyncClient, member_id: MemberId, text: str
) -> httpx.Response:
    settings = get_settings()
    voice = get_member(member_id).voice.elevenlabs

    request = client.build_request(
        "POST",
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice.voice_id}/stream",
        params={"output_format": "mp3_22050_32"},
        headers={"xi-api-key": settings.elevenlabs_api_key},
        json={
            "text": text,
            # Flash is the low-latency model; quality loss is inaudible on a call.
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": voice.stability,
                "style": voice.style,
                "speed": voice.speed,
                "use_speaker_boost": True,
            },
        },
    )
    return await _open_stream(client, "elevenlabs", request)


async def _deepgram_request(
    client: httpx.AsyncClient, member_id: MemberId, text: str
) -> httpx.Response:
    settings = get_settings()
    voice = get_member(member_id).voice.deepgram

    request = client.build_request(
        "POST",
        "https://api.deepgram.com/v1/speak",
        params={"model": voice.model, "encoding": "mp3"},
        headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        json={"text": text},
    )
    return await _open_stream(client, "deepgram", request)


_IMPLEMENTATIONS: dict[TtsProviderName, Callable] = {
    "elevenlabs": _elevenlabs_request,
    "deepgram": _deepgram_request,
}


async def synthesize(log, member_id: MemberId, text: str) -> SynthesisResult:
    """Synthesise ``text`` in the given member's voice.

    Walks the configured provider chain until one answers. Raises only when
    every provider has failed — at which point the board genuinely cannot speak.
    """
    settings = get_settings()
    fell_back_from: list[TtsProviderName] = []
    failures: list[str] = []

    client = httpx.AsyncClient(timeout=SYNTH_TIMEOUT_S)

    for provider in settings.tts_chain:
        if breaker.is_open(provider):
            # Skipping costs nothing; attempting a known-dead provider costs ~600ms.
            log.debug(
                f"{provider} circuit open — skipping",
                provider=provider,
                reason=breaker.reason_for(provider),
            )
            fell_back_from.append(provider)
            failures.append(f"{provider}: circuit open ({breaker.reason_for(provider)})")
            continue

        started = time.perf_counter()

        try:
            result = await timed(
                log,
                "tts.ttfb",
                lambda p=provider: _IMPLEMENTATIONS[p](client, member_id, text),
                budget_ms=400,
                provider=provider,
                member_id=member_id,
                chars=len(text),
            )
        except Exception as exc:
            kind: FailureKind = exc.kind if isinstance(exc, TtsError) else "transient"
            reason = str(exc)
            tripped = breaker.record_failure(provider, kind, reason)

            log.error(
                f"TTS provider {provider} failed ({kind})"
                + (f" — circuit open for {COOLDOWN_MS[kind] // 1000}s" if tripped else ""),
                provider=provider,
                kind=kind,
                tripped=tripped,
                cooldown_ms=COOLDOWN_MS[kind] if tripped else 0,
                error=reason,
            )
            fell_back_from.append(provider)
            failures.append(f"{provider}: {reason}")
            continue

        response = result.value
        breaker.record_success(provider)

        if fell_back_from:
            log.warning(
                f"TTS fell back to {provider} after {', '.join(fell_back_from)} failed",
                provider=provider,
                fell_back_from=fell_back_from,
                failures=failures,
            )

        async def _chunks(resp=response, cli=client):
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await cli.aclose()

        async def _aclose(resp=response, cli=client):
            await resp.aclose()
            await cli.aclose()

        return SynthesisResult(
            provider=provider,
            chunks=_chunks(),
            content_type="audio/mpeg",
            ttfb_ms=round((time.perf_counter() - started) * 1000),
            fell_back_from=fell_back_from,
            _aclose=_aclose,
        )

    await client.aclose()
    detail = "\n".join(f"  - {f}" for f in failures)
    raise RuntimeError(f"Every TTS provider failed — the board cannot speak.\n{detail}")


async def synthesize_to_bytes(log, member_id: MemberId, text: str) -> tuple[bytes, SynthesisResult]:
    """Collect a synthesis into memory. For tests and previews, not the hot path."""
    result = await synthesize(log, member_id, text)
    audio = b"".join([chunk async for chunk in result.chunks])
    return audio, result
