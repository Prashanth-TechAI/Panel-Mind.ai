"""Provider health probes.

Every external dependency gets a probe that answers one question: if an
interview started right now, would this provider carry it? A key that
authenticates but has no credits left is NOT healthy, so the deep probe
exercises the real operation rather than just the auth handshake.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Literal

import httpx

from app.config import get_settings
from app.logging_setup import get_logger

ProbeStatus = Literal["ok", "degraded", "down"]

PROBE_TIMEOUT_S = 6.0

# A line the length of a real board question.
#
# The probe must cost what production costs. An earlier version synthesised a
# single "." — it returned 200 on an account with under 24 credits left, while
# every actual question failed with quota_exceeded. A probe that passes where
# production fails is worse than no probe at all.
ELEVENLABS_PROBE_TEXT = (
    "Please come in and have a seat. Tell us briefly what brought you here today."
)

_CREDITS_LEFT = re.compile(r"You have (\d+) credits remaining")


@dataclass(slots=True)
class ProbeResult:
    name: str
    role: str
    status: ProbeStatus
    latency_ms: int = 0
    http_status: int | None = None
    detail: str | None = None
    # Actionable next step when not ok. Surfaced straight to the operator.
    hint: str | None = None


@dataclass(slots=True)
class HealthReport:
    status: ProbeStatus
    checked_at: str
    deep: bool
    total_ms: int
    providers: list[ProbeResult] = field(default_factory=list)


async def _probe_groq(client: httpx.AsyncClient, _deep: bool) -> ProbeResult:
    s = get_settings()
    response = await client.get(
        f"{s.groq_base_url}/models", headers={"Authorization": f"Bearer {s.groq_api_key}"}
    )

    if response.status_code >= 400:
        return ProbeResult(
            "groq",
            "hot-path LLM",
            "down",
            http_status=response.status_code,
            detail=f"models endpoint returned {response.status_code}",
            hint="Check GROQ_API_KEY.",
        )

    ids = {m.get("id") for m in response.json().get("data", [])}
    available = s.groq_model in ids

    return ProbeResult(
        "groq",
        "hot-path LLM",
        "ok" if available else "degraded",
        http_status=response.status_code,
        detail=(
            f"model {s.groq_model} available"
            if available
            else f"configured model {s.groq_model} not in account's model list"
        ),
        hint=None if available else "Set GROQ_MODEL to a model your account can access.",
    )


async def _probe_openrouter(client: httpx.AsyncClient, _deep: bool) -> ProbeResult:
    s = get_settings()
    response = await client.get(
        f"{s.openrouter_base_url}/key",
        headers={"Authorization": f"Bearer {s.openrouter_api_key}"},
    )

    if response.status_code >= 400:
        return ProbeResult(
            "openrouter",
            "eval-plane LLM",
            "down",
            http_status=response.status_code,
            detail=f"key endpoint returned {response.status_code}",
            hint="Check OPENROUTER_API_KEY.",
        )

    data = response.json().get("data", {}) or {}
    limit = data.get("limit")
    usage = data.get("usage", 0) or 0
    exhausted = limit is not None and usage >= limit

    return ProbeResult(
        "openrouter",
        "eval-plane LLM",
        "down" if exhausted else "ok",
        http_status=response.status_code,
        detail=(
            f"credit limit reached ({usage}/{limit})"
            if exhausted
            else f"model {s.openrouter_model}, usage {usage}"
            + ("" if limit is None else f"/{limit}")
        ),
        hint="Top up OpenRouter credits." if exhausted else None,
    )


async def _probe_deepgram(client: httpx.AsyncClient, _deep: bool) -> ProbeResult:
    s = get_settings()
    response = await client.get(
        "https://api.deepgram.com/v1/projects",
        headers={"Authorization": f"Token {s.deepgram_api_key}"},
    )

    if response.status_code >= 400:
        return ProbeResult(
            "deepgram",
            "STT + fallback TTS",
            "down",
            http_status=response.status_code,
            detail=f"projects endpoint returned {response.status_code}",
            hint="Check DEEPGRAM_API_KEY.",
        )

    return ProbeResult("deepgram", "STT + fallback TTS", "ok", http_status=response.status_code)


async def _probe_elevenlabs(client: httpx.AsyncClient, deep: bool) -> ProbeResult:
    """ElevenLabs needs a deep probe to be meaningful.

    The voices endpoint succeeds on a key with zero credits left, so a shallow
    check reports a healthy provider that cannot speak a single word.
    """
    s = get_settings()
    headers = {"xi-api-key": s.elevenlabs_api_key}

    voices_res = await client.get("https://api.elevenlabs.io/v1/voices", headers=headers)

    if voices_res.status_code >= 400:
        return ProbeResult(
            "elevenlabs",
            "primary TTS",
            "down",
            http_status=voices_res.status_code,
            detail=f"voices endpoint returned {voices_res.status_code}",
            hint="Check ELEVENLABS_API_KEY.",
        )

    voice_count = len(voices_res.json().get("voices", []))

    if not deep:
        return ProbeResult(
            "elevenlabs",
            "primary TTS",
            "ok",
            http_status=voices_res.status_code,
            detail=f"{voice_count} voices reachable (auth only — add ?deep=1 to verify quota)",
        )

    synth_res = await client.post(
        "https://api.elevenlabs.io/v1/text-to-speech/yRis6UiS4dtT4Aqv72DC",
        params={"output_format": "mp3_22050_32"},
        headers={**headers, "Content-Type": "application/json"},
        json={"text": ELEVENLABS_PROBE_TEXT, "model_id": "eleven_flash_v2_5"},
    )

    if synth_res.status_code < 400:
        return ProbeResult(
            "elevenlabs",
            "primary TTS",
            "ok",
            http_status=synth_res.status_code,
            detail=(
                f"{voice_count} voices, synthesised {len(ELEVENLABS_PROBE_TEXT)} chars "
                f"-> {len(synth_res.content)} bytes"
            ),
        )

    body = synth_res.text
    is_quota = "quota_exceeded" in body
    match = _CREDITS_LEFT.search(body)
    remaining = match.group(1) if match else "unknown"

    return ProbeResult(
        "elevenlabs",
        "primary TTS",
        "down",
        http_status=synth_res.status_code,
        detail=(
            f"credits exhausted ({remaining} remaining) — authenticates but cannot "
            "synthesise a full question"
            if is_quota
            else body[:200]
        ),
        hint=(
            "Top up ElevenLabs credits. Until then the board falls back to Deepgram Aura voices."
            if is_quota
            else "Inspect the ElevenLabs error detail."
        ),
    )


async def _probe_livekit(_client: httpx.AsyncClient, _deep: bool) -> ProbeResult:
    from livekit import api

    s = get_settings()
    lk = api.LiveKitAPI(s.livekit_http_url, s.livekit_api_key, s.livekit_api_secret)

    try:
        # Exercises URL, key and secret together — a bad secret fails here even
        # though a plain HTTPS GET against the host would return 200.
        rooms = await lk.room.list_rooms(api.ListRoomsRequest())
        return ProbeResult(
            "livekit", "realtime transport", "ok", detail=f"{len(rooms.rooms)} active room(s)"
        )
    finally:
        await lk.aclose()


async def _probe_postgres(_client: httpx.AsyncClient, _deep: bool) -> ProbeResult:
    """Storage health. Not configured is a warning, not a failure."""
    from app import db

    if not db.is_configured():
        return ProbeResult(
            "postgres",
            "storage",
            "degraded",
            detail="not configured — using on-disk JSON",
            hint="Set DATABASE_URL to your local Postgres.",
        )

    ok, detail = await db.ping()
    return ProbeResult(
        "postgres",
        "storage",
        "ok" if ok else "down",
        detail=detail,
        hint=None if ok else "Is Postgres running? Check DATABASE_URL and the role's password.",
    )


_PROBES = [
    ("groq", _probe_groq),
    ("openrouter", _probe_openrouter),
    ("deepgram", _probe_deepgram),
    ("elevenlabs", _probe_elevenlabs),
    ("livekit", _probe_livekit),
    ("postgres", _probe_postgres),
]


def _worst(results: list[ProbeResult]) -> ProbeStatus:
    if any(r.status == "down" for r in results):
        return "down"
    if any(r.status == "degraded" for r in results):
        return "degraded"
    return "ok"


async def probe_all(*, deep: bool = False) -> HealthReport:
    log = get_logger(component="health")
    started = time.perf_counter()

    log.info(f"running provider health probes (deep={deep})", deep=deep)

    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:

        async def run(name: str, probe) -> ProbeResult:
            probe_started = time.perf_counter()
            try:
                result = await probe(client, deep)
            except Exception as exc:
                return ProbeResult(
                    name,
                    "unknown",
                    "down",
                    latency_ms=round((time.perf_counter() - probe_started) * 1000),
                    detail=str(exc)[:300],
                    hint="Provider unreachable or credentials rejected.",
                )
            result.latency_ms = round((time.perf_counter() - probe_started) * 1000)
            return result

        providers = await asyncio.gather(*(run(name, probe) for name, probe in _PROBES))

    report = HealthReport(
        status=_worst(list(providers)),
        checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        deep=deep,
        total_ms=round((time.perf_counter() - started) * 1000),
        providers=list(providers),
    )

    unhealthy = [p for p in report.providers if p.status != "ok"]
    if unhealthy:
        log.warning(
            f"{len(unhealthy)} provider(s) not healthy",
            unhealthy=[{"name": p.name, "status": p.status, "detail": p.detail} for p in unhealthy],
        )
    else:
        log.info("all providers healthy", total_ms=report.total_ms)

    return report
