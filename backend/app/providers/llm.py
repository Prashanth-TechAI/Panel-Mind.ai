"""LLM access, split by tier.

hot     — Groq. Drives the conversation. Must return inside ~300ms, so it gets
          one fast retry at most; a slow success is a failure here.
digest  — Groq, smaller model. Rolling context summaries between blocks.
cold    — OpenRouter. The evaluators. Runs off the critical path, so it trades
          latency for quality and retries properly.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.logging_setup import Stage, timed

Tier = Literal["hot", "digest", "cold"]
Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class ChatResult:
    text: str
    model: str
    tier: Tier
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True, slots=True)
class _TierSettings:
    timeout_s: float
    max_retries: int
    budget_ms: int  # logged as over-budget above this
    stage: Stage


_TIERS: dict[Tier, _TierSettings] = {
    # One retry only: on the hot path a second attempt already costs more than
    # the budget allows, so the caller falls back to a filler utterance instead.
    "hot": _TierSettings(4.0, 1, 400, "llm.hot"),
    "digest": _TierSettings(6.0, 1, 1_500, "llm.digest"),
    "cold": _TierSettings(90.0, 3, 30_000, "llm.cold"),
}

_RETRYABLE_STATUSES = {408, 409, 429, 500, 502, 503, 504}


class LlmError(Exception):
    def __init__(
        self, message: str, tier: Tier, status: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.tier = tier
        self.status = status
        self.retryable = retryable


def _endpoint(tier: Tier) -> tuple[str, str, str]:
    s = get_settings()
    if tier == "cold":
        return f"{s.openrouter_base_url}/chat/completions", s.openrouter_api_key, s.openrouter_model
    if tier == "digest":
        return f"{s.groq_base_url}/chat/completions", s.groq_api_key, s.groq_summary_model
    return f"{s.groq_base_url}/chat/completions", s.groq_api_key, s.groq_model


async def _call_once(
    tier: Tier,
    messages: list[ChatMessage],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
    timeout_s: float,
) -> ChatResult:
    url, api_key, model = _endpoint(tier)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [m.as_dict() for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    started = asyncio.get_running_loop().time()

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise LlmError(f"{tier} LLM timed out after {timeout_s}s", tier, retryable=True) from exc
    except httpx.HTTPError as exc:
        raise LlmError(f"{tier} LLM request failed: {exc}", tier, retryable=True) from exc

    if response.status_code >= 400:
        body = response.text[:300]
        raise LlmError(
            f"{tier} LLM returned {response.status_code}: {body}",
            tier,
            response.status_code,
            response.status_code in _RETRYABLE_STATUSES,
        )

    body = response.json()
    choices = body.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else None

    if not isinstance(content, str):
        raise LlmError(f"{tier} LLM returned no content", tier, response.status_code, True)

    usage = body.get("usage") or {}
    return ChatResult(
        text=content.strip(),
        model=model,
        tier=tier,
        duration_ms=round((asyncio.get_running_loop().time() - started) * 1000),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )


async def chat(
    log,
    tier: Tier,
    messages: list[ChatMessage],
    *,
    temperature: float = 0.7,
    max_tokens: int = 300,
    json_mode: bool = False,
    timeout_s: float | None = None,
) -> ChatResult:
    settings = _TIERS[tier]
    last_error: Exception | None = None

    for attempt in range(settings.max_retries + 1):
        try:
            result = await timed(
                log,
                settings.stage,
                lambda: _call_once(
                    tier,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    timeout_s=timeout_s or settings.timeout_s,
                ),
                budget_ms=settings.budget_ms,
                attempt=attempt,
                message_count=len(messages),
            )
            return result.value
        except Exception as exc:
            last_error = exc
            retryable = exc.retryable if isinstance(exc, LlmError) else True

            if not retryable or attempt == settings.max_retries:
                break

            backoff_ms = 250 * (2**attempt)
            log.warning(
                f"{tier} LLM retrying in {backoff_ms}ms",
                tier=tier,
                attempt=attempt,
                backoff_ms=backoff_ms,
                error=str(exc),
            )
            await asyncio.sleep(backoff_ms / 1000)

    assert last_error is not None
    raise last_error


async def _call_vision(content: list[dict], *, max_tokens: int = 4000) -> str:
    """One vision call on the cold tier.

    Kept separate from `chat` because image parts are not plain strings and the
    ChatMessage dataclass would flatten them.
    """
    url, api_key, model = _endpoint("cold")

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": max_tokens,
            },
        )

    if response.status_code >= 400:
        raise LlmError(f"vision call returned {response.status_code}: {response.text[:300]}", "cold")

    return response.json()["choices"][0]["message"]["content"]


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Strip ```json fences some models add despite JSON mode."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


TModel = TypeVar("TModel", bound=BaseModel)


def _describe(error: Exception) -> str:
    """Render validation failures as instructions the model can act on."""
    if isinstance(error, ValidationError):
        lines = []
        for issue in error.errors()[:8]:
            where = ".".join(str(p) for p in issue["loc"])
            lines.append(f"- field `{where}`: {issue['msg']}")
        return "\n".join(lines)
    return f"- the response was not valid JSON: {error}"


async def chat_model(
    log,
    tier: Tier,
    messages: list[ChatMessage],
    schema: type[TModel],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1200,
) -> tuple[TModel, ChatResult]:
    """Chat with a schema-validated JSON result.

    A model that returns malformed JSON gets one corrective retry with its own
    bad output echoed back, which recovers the overwhelming majority of cases.
    """
    result = await chat(
        log, tier, messages, temperature=temperature, max_tokens=max_tokens, json_mode=True
    )

    def parse(raw: str) -> TModel:
        return schema.model_validate(json.loads(_strip_fences(raw)))

    try:
        return parse(result.text), result
    except (ValidationError, json.JSONDecodeError) as first_error:
        log.warning(
            f"{tier} LLM JSON failed validation — retrying with correction",
            tier=tier,
            error=str(first_error)[:400],
        )
        faults = _describe(first_error)

    corrected = await chat(
        log,
        tier,
        [
            *messages,
            ChatMessage("assistant", result.text),
            # Naming the exact field and constraint is what makes the retry
            # work. A bare "that was wrong" reproduces the same output.
            ChatMessage(
                "user",
                "That JSON did not match the required schema. Fix exactly these "
                f"problems:\n{faults}\n\n"
                "Return ONLY corrected JSON. No prose, no code fences.",
            ),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
    )

    try:
        return parse(corrected.text), corrected
    except (ValidationError, json.JSONDecodeError) as exc:
        raise LlmError(f"{tier} LLM JSON failed validation twice: {exc}", tier) from exc
