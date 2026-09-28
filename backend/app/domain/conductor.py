"""The Conductor.

One rule holds the whole system together: exactly one member holds the mic
token at any instant, and only the Conductor grants it. Members cannot take the
mic, only release it. That makes talk-over structurally impossible rather than
merely unlikely — which is the difference between a demo and a product.

This module is a pure reducer. No network, no clock, no randomness: the caller
supplies ``at_ms`` on every event. That makes the full interview flow —
including every timeout and edge case — testable without a live session.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from app.domain.board import CHAIRMAN_ID, MEMBER_IDS, QUESTIONING_ORDER, MemberId

Phase = Literal["idle", "chairman_opening", "member_block", "chairman_closing", "ended"]

# What the active member's LLM reports back after speaking.
MemberSignal = Literal["FOLLOWUP", "PROBE_HARDER", "DONE"]

SpeakIntent = Literal[
    "opening",
    "seed",
    "followup",
    "probe_harder",
    "interrupt",
    "handover_out",
    "handover_in",
    "closing",
]


@dataclass(frozen=True, slots=True)
class ConductorState:
    phase: Phase = "idle"
    # The single member permitted to speak. None only when idle or ended.
    mic_holder: MemberId | None = None
    started_at_ms: int | None = None
    now_ms: int = 0
    block_started_at_ms: int | None = None
    # Questions asked in the current block, including the seed question.
    questions_in_block: int = 0
    completed_blocks: tuple[MemberId, ...] = ()
    # Members still awaiting a block, in call order.
    pending_members: tuple[MemberId, ...] = QUESTIONING_ORDER
    # Rolling context handed to the next member so the board feels like one board.
    digest: str = ""
    ended_reason: str | None = None


# --- Events ---


@dataclass(frozen=True, slots=True)
class Start:
    at_ms: int


@dataclass(frozen=True, slots=True)
class MemberSignalEvent:
    signal: MemberSignal
    at_ms: int


@dataclass(frozen=True, slots=True)
class AspirantSpoke:
    at_ms: int
    word_count: int


@dataclass(frozen=True, slots=True)
class DigestUpdated:
    digest: str
    at_ms: int


@dataclass(frozen=True, slots=True)
class Tick:
    at_ms: int


@dataclass(frozen=True, slots=True)
class Abort:
    reason: str
    at_ms: int


ConductorEvent = Start | MemberSignalEvent | AspirantSpoke | DigestUpdated | Tick | Abort


# --- Effects ---


@dataclass(frozen=True, slots=True)
class Speak:
    member_id: MemberId
    intent: SpeakIntent
    digest: str
    type: str = "SPEAK"


@dataclass(frozen=True, slots=True)
class GrantMic:
    to: MemberId
    digest: str
    reason: str
    type: str = "GRANT_MIC"


@dataclass(frozen=True, slots=True)
class End:
    reason: str
    type: str = "END"


Effect = Speak | GrantMic | End


@dataclass(frozen=True, slots=True)
class ConductorConfig:
    # Hard ceiling on the whole interview.
    total_budget_ms: int = 28 * 60_000
    chairman_opening_ms: int = 4 * 60_000
    member_block_ms: int = 5 * 60_000
    # Seed question plus follow-ups. A real board is relentless: in a recorded
    # UPSC mock the Chairman alone asked ~15 and the science member ~12, mostly
    # short factual probes fired back to back. Six made ours feel like a survey.
    max_questions_per_block: int = 16
    # Answers longer than this get interrupted, as a real board would.
    # Real boards cut in earlier than this; candidates who run long lose marks.
    max_answer_words: int = 150


# Budgets tuned to a real UPSC personality test: roughly half an hour, the
# Chairman opening and closing, four members with a substantial block each.
DEFAULT_CONFIG = ConductorConfig()


@dataclass(frozen=True, slots=True)
class Transition:
    state: ConductorState
    effects: list[Effect] = field(default_factory=list)


def initial_state() -> ConductorState:
    return ConductorState()


def elapsed_ms(state: ConductorState) -> int:
    return 0 if state.started_at_ms is None else state.now_ms - state.started_at_ms


def _block_elapsed_ms(state: ConductorState) -> int:
    return 0 if state.block_started_at_ms is None else state.now_ms - state.block_started_at_ms


def _current_block_budget_ms(state: ConductorState, config: ConductorConfig) -> int:
    """Time budget for whichever block is currently running."""
    if state.phase == "chairman_opening":
        return config.chairman_opening_ms
    return config.member_block_ms


def block_exhausted(state: ConductorState, config: ConductorConfig) -> tuple[bool, str]:
    """Whether the active member has exhausted either budget for their block."""
    if state.questions_in_block >= config.max_questions_per_block:
        return True, "question_limit"
    if _block_elapsed_ms(state) >= _current_block_budget_ms(state, config):
        return True, "time_limit"
    return False, ""


def _advance_block(state: ConductorState, config: ConductorConfig, reason: str) -> Transition:
    """Move the mic on: to the next pending member, or to the Chairman to close.

    Emits the spoken handover so the transition is audible to the candidate
    rather than a silent cut.
    """
    outgoing = state.mic_holder
    effects: list[Effect] = []

    if outgoing is not None:
        effects.append(Speak(member_id=outgoing, intent="handover_out", digest=state.digest))

    completed = state.completed_blocks
    if outgoing is not None and outgoing not in completed:
        completed = (*completed, outgoing)

    out_of_time = elapsed_ms(state) >= config.total_budget_ms
    next_member = state.pending_members[0] if state.pending_members else None
    rest = state.pending_members[1:]

    # Out of time, or every member has had their turn: the Chairman closes.
    if out_of_time or next_member is None:
        effects.append(
            GrantMic(
                to=CHAIRMAN_ID,
                digest=state.digest,
                reason="total_time_limit" if out_of_time else reason,
            )
        )
        effects.append(Speak(member_id=CHAIRMAN_ID, intent="closing", digest=state.digest))
        return Transition(
            state=replace(
                state,
                phase="chairman_closing",
                mic_holder=CHAIRMAN_ID,
                block_started_at_ms=state.now_ms,
                questions_in_block=0,
                completed_blocks=completed,
                pending_members=() if out_of_time else state.pending_members,
            ),
            effects=effects,
        )

    effects.append(GrantMic(to=next_member, digest=state.digest, reason=reason))
    effects.append(Speak(member_id=CHAIRMAN_ID, intent="handover_in", digest=state.digest))
    effects.append(Speak(member_id=next_member, intent="seed", digest=state.digest))

    return Transition(
        state=replace(
            state,
            phase="member_block",
            mic_holder=next_member,
            block_started_at_ms=state.now_ms,
            questions_in_block=1,
            completed_blocks=completed,
            pending_members=rest,
        ),
        effects=effects,
    )


def _end(state: ConductorState, reason: str) -> Transition:
    return Transition(
        state=replace(state, phase="ended", mic_holder=None, ended_reason=reason),
        effects=[End(reason=reason)],
    )


def reduce(
    state: ConductorState,
    event: ConductorEvent,
    config: ConductorConfig = DEFAULT_CONFIG,
) -> Transition:
    # Time only moves forward. A stale event must not rewind the session clock.
    current = replace(state, now_ms=max(state.now_ms, event.at_ms))

    if current.phase == "ended":
        return Transition(state=current)

    match event:
        case Start():
            if current.phase != "idle":
                return Transition(state=current)
            return Transition(
                state=replace(
                    current,
                    phase="chairman_opening",
                    mic_holder=CHAIRMAN_ID,
                    started_at_ms=event.at_ms,
                    block_started_at_ms=event.at_ms,
                    questions_in_block=1,
                ),
                effects=[
                    GrantMic(to=CHAIRMAN_ID, digest="", reason="session_start"),
                    Speak(member_id=CHAIRMAN_ID, intent="opening", digest=""),
                ],
            )

        case Abort():
            return _end(current, event.reason)

        case DigestUpdated():
            return Transition(state=replace(current, digest=event.digest))

        case AspirantSpoke():
            if current.mic_holder is None:
                return Transition(state=current)
            # Rambling gets cut off mid-thought, exactly as a real board would.
            if event.word_count > config.max_answer_words:
                return Transition(
                    state=current,
                    effects=[
                        Speak(
                            member_id=current.mic_holder,
                            intent="interrupt",
                            digest=current.digest,
                        )
                    ],
                )
            return Transition(state=current)

        case MemberSignalEvent():
            if current.mic_holder is None:
                return Transition(state=current)

            if current.phase == "chairman_closing":
                # The closing is one utterance, not a block. Once the Chairman
                # has said his piece the interview is over — waiting for an
                # explicit DONE left it hanging until the total time budget.
                return _end(current, "interview_complete")

            exhausted, reason = block_exhausted(current, config)

            if event.signal == "DONE" or exhausted:
                return _advance_block(
                    current, config, "member_done" if event.signal == "DONE" else reason
                )

            intent: SpeakIntent = (
                "probe_harder" if event.signal == "PROBE_HARDER" else "followup"
            )
            return Transition(
                state=replace(current, questions_in_block=current.questions_in_block + 1),
                effects=[
                    Speak(member_id=current.mic_holder, intent=intent, digest=current.digest)
                ],
            )

        case Tick():
            if current.phase == "idle":
                return Transition(state=current)

            # Hard stop: the session has run over its total budget.
            if (
                elapsed_ms(current) >= config.total_budget_ms
                and current.phase != "chairman_closing"
            ):
                return _advance_block(current, config, "total_time_limit")

            # Closing runs over: end it outright rather than looping.
            if (
                current.phase == "chairman_closing"
                and elapsed_ms(current) >= config.total_budget_ms + config.member_block_ms
            ):
                return _end(current, "closing_overran")

            exhausted, reason = block_exhausted(current, config)
            if exhausted and current.phase != "chairman_closing":
                return _advance_block(current, config, reason)

            return Transition(state=current)

    raise AssertionError(f"Unhandled conductor event: {event!r}")


def assert_invariants(state: ConductorState) -> None:
    """Invariants that must hold after every transition.

    Called from tests and from the live session loop as a runtime assertion — if
    one of these ever trips in production, two members are about to speak at
    once and it is better to fail loudly than to ship the overlap.
    """
    active = state.phase not in ("idle", "ended")

    if active and state.mic_holder is None:
        raise AssertionError(f"Invariant violated: phase '{state.phase}' has no mic holder")

    if not active and state.mic_holder is not None:
        raise AssertionError(
            f"Invariant violated: phase '{state.phase}' must not hold the mic "
            f"(has {state.mic_holder})"
        )

    if state.mic_holder is not None and state.mic_holder not in MEMBER_IDS:
        raise AssertionError(f"Invariant violated: unknown mic holder '{state.mic_holder}'")

    if len(set(state.completed_blocks)) != len(state.completed_blocks):
        raise AssertionError(
            f"Invariant violated: a member completed two blocks "
            f"({', '.join(state.completed_blocks)})"
        )

    if any(m in state.completed_blocks for m in state.pending_members):
        raise AssertionError("Invariant violated: a completed member is still pending")
