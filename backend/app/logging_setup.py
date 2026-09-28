"""Structured logging.

Two things matter for this system and both are baked in here:

1. Correlation. Every log line carries the session_id and turn_id it belongs
   to, so one interview can be reconstructed end to end from the log stream.

2. Latency. The hot path has an ~800ms budget from end-of-speech to first
   audio out. ``timed()`` stamps every provider call with its real duration,
   so when the budget is blown you can see exactly which stage ate it.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

import structlog

Stage = Literal[
    "stt.final",
    "turn.detect",
    "llm.hot",
    "llm.digest",
    "llm.cold",
    "tts.ttfb",
    "tts.total",
    "conductor.route",
    "http",
]

_LEVEL_MAP = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}

_SECRET_KEYS = {"api_key", "apikey", "authorization", "xi-api-key", "secret", "token"}

_configured = False


def _redact_secrets(_logger: Any, _name: str, event_dict: dict) -> dict:
    """Never let a credential reach the log stream."""
    for key in list(event_dict):
        if key.lower().replace("_", "") in {s.replace("_", "").replace("-", "") for s in _SECRET_KEYS}:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(level: str = "info", pretty: bool | None = None) -> None:
    """Idempotent logging setup. Pretty console in dev, JSON lines in prod."""
    global _configured

    py_level = _LEVEL_MAP.get(level, logging.INFO)
    if pretty is None:
        pretty = sys.stderr.isatty()

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=py_level, force=True)

    renderer: Any = (
        structlog.dev.ConsoleRenderer(colors=True)
        if pretty
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(py_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(**context: Any) -> structlog.stdlib.BoundLogger:
    """Logger that stamps every line with the given correlation context."""
    if not _configured:
        configure_logging()
    return structlog.get_logger().bind(**context)


def new_id(prefix: str) -> str:
    """Short unique id. Not cryptographic — for correlation only."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


T = TypeVar("T")


@dataclass(slots=True)
class Timed[TValue]:
    value: TValue
    duration_ms: int


@asynccontextmanager
async def timed_block(
    log: Any,
    stage: Stage,
    *,
    budget_ms: int | None = None,
    **detail: Any,
):
    """Time a block and log its duration, flagging anything over budget."""
    started = time.perf_counter()
    try:
        yield
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        log.error(
            f"{stage} FAILED after {duration_ms}ms",
            stage=stage,
            duration_ms=duration_ms,
            error=str(exc),
            **detail,
        )
        raise
    else:
        duration_ms = round((time.perf_counter() - started) * 1000)
        over = budget_ms is not None and duration_ms > budget_ms
        message = (
            f"{stage} took {duration_ms}ms — OVER budget of {budget_ms}ms"
            if over
            else f"{stage} {duration_ms}ms"
        )
        (log.warning if over else log.debug)(
            message,
            stage=stage,
            duration_ms=duration_ms,
            budget_ms=budget_ms,
            over_budget=over,
            **detail,
        )


async def timed(
    log: Any,
    stage: Stage,
    fn: Callable[[], Awaitable[T]],
    *,
    budget_ms: int | None = None,
    **detail: Any,
) -> Timed[T]:
    """Run an async operation and log how long it took.

    Logs at ``debug`` when the call succeeds inside its budget, ``warning``
    when it exceeds ``budget_ms``, and ``error`` when it raises — always with
    the duration attached, because a slow failure and a fast failure are
    different bugs.
    """
    started = time.perf_counter()
    try:
        value = await fn()
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        log.error(
            f"{stage} FAILED after {duration_ms}ms",
            stage=stage,
            duration_ms=duration_ms,
            error=str(exc),
            error_type=type(exc).__name__,
            **detail,
        )
        raise

    duration_ms = round((time.perf_counter() - started) * 1000)
    over = budget_ms is not None and duration_ms > budget_ms
    message = (
        f"{stage} took {duration_ms}ms — OVER budget of {budget_ms}ms"
        if over
        else f"{stage} {duration_ms}ms"
    )
    (log.warning if over else log.debug)(
        message,
        stage=stage,
        duration_ms=duration_ms,
        budget_ms=budget_ms,
        over_budget=over,
        **detail,
    )
    return Timed(value=value, duration_ms=duration_ms)
