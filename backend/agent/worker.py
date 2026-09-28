"""LiveKit voice worker.

Run alongside the API:

    uv run python -m agent.worker dev

One job per interview. The worker resolves the session from the room name,
loads the prepared question trees, seats the five members, and hands control
to the Conductor.
"""

from __future__ import annotations

import asyncio
import os

import httpx
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.inference import TurnDetector
from livekit.plugins import deepgram, openai, silero

from app.config import get_settings
from app.domain.daf import Daf
from app.domain.questions import MemberQuestionTree
from app.logging_setup import configure_logging, get_logger
from agent.board_agent import (
    BoardOrchestrator,
    build_agents,
    build_cursors,
)

# How often the Conductor is nudged so time-based handovers fire even while
# the candidate is silent.
TICK_INTERVAL_S = 5.0

# The control plane this worker resolves sessions from.
API_BASE = os.environ.get("BOARD_API_URL", "http://127.0.0.1:8000")


async def _load_session(room_name: str) -> tuple[str, Daf, list[MemberQuestionTree]]:
    """Fetch the prepared material for this room from the control plane."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{API_BASE}/api/session/by-room/{room_name}")
        response.raise_for_status()
        body = response.json()

    return (
        body["session_id"],
        Daf.model_validate(body["daf"]),
        [MemberQuestionTree.model_validate(t) for t in body["trees"]],
    )


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger(component="worker", room=ctx.room.name)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    log.info("worker connected, resolving session")

    try:
        session_id, daf, trees = await _load_session(ctx.room.name)
    except Exception as exc:
        log.error("no prepared session for this room — refusing the job", error=str(exc))
        return

    agents = build_agents(daf)
    cursors = build_cursors(trees)

    session = AgentSession(
        stt=deepgram.STT(
            api_key=settings.deepgram_api_key,
            model="nova-3",
            language="en-IN",
            # Tight endpointing; the semantic detector below decides the real
            # end of turn, so this only needs to close the audio segment.
            endpointing_ms=25,
            interim_results=True,
            punctuate=True,
        ),
        # Groq is OpenAI-compatible, and its speed is why the turn budget works.
        llm=openai.LLM(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        ),
        vad=silero.VAD.load(),
        # Semantic end-of-turn: knows a pause mid-thought from a finished
        # answer. A silence timer would cut candidates off constantly.
        turn_detection=TurnDetector(),
        min_endpointing_delay=0.4,
        max_endpointing_delay=4.0,
    )

    orchestrator = BoardOrchestrator(
        session=session,
        room=ctx.room,
        daf=daf,
        agents=agents,
        cursors=cursors,
        session_id=session_id,
        api_base=API_BASE,
    )

    @session.on("user_input_transcribed")
    def _on_transcript(event) -> None:
        if not getattr(event, "is_final", False):
            return
        transcript = (getattr(event, "transcript", "") or "").strip()
        if not transcript:
            return
        # The handler is sync; the work is not.
        asyncio.create_task(orchestrator.on_candidate_turn(transcript))

    # The Chairman opens, so the session starts on M0.
    await session.start(agent=agents["M0"], room=ctx.room)

    log.info(
        "board seated",
        candidate=daf.full_name,
        prepared=[t.member_id for t in trees],
    )

    # A candidate who walks out ends the interview. Without this the tick loop
    # keeps nudging a dead room until the total time budget expires, logging
    # "engine is closed" every few seconds.
    walked_out = asyncio.Event()

    @ctx.room.on("disconnected")
    def _on_disconnected(*_args) -> None:
        log.info("candidate left the room")
        walked_out.set()

    await orchestrator.begin()

    # Nudge the Conductor so block and total time limits fire even in silence.
    while not orchestrator.ended and not walked_out.is_set():
        try:
            await asyncio.wait_for(walked_out.wait(), timeout=TICK_INTERVAL_S)
            break
        except TimeoutError:
            await orchestrator.tick()

    if walked_out.is_set() and not orchestrator.ended:
        await orchestrator.abandon("candidate_left")

    log.info("interview complete", reason=orchestrator.state.ended_reason)
    await session.aclose()


def main() -> None:
    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
        )
    )


if __name__ == "__main__":
    main()
