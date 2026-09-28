"""The live board.

Five ``Agent`` instances share one ``AgentSession``. Only the one holding the
mic is the session's current agent, so LiveKit itself enforces the invariant
the Conductor asserts: exactly one member can speak at any instant.

The hot path never invents a question. Each member walks its pre-generated
question tree and the LLM only rephrases the next node in that member's voice,
which is what keeps a turn inside its budget.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
from dataclasses import dataclass, field
from typing import Literal

from livekit import rtc
from livekit.agents import Agent, AgentSession
from livekit.plugins import elevenlabs
from pydantic import BaseModel, Field

from app.config import get_settings
from app.domain.board import BOARD, BOARD_CONDUCT, MemberId, get_member
from app.domain.conductor import (
    DEFAULT_CONFIG,
    Abort,
    AspirantSpoke,
    ConductorState,
    Effect,
    End,
    GrantMic,
    MemberSignalEvent,
    Speak,
    SpeakIntent,
    Start,
    Tick,
    assert_invariants,
    initial_state,
    reduce,
)
from app.domain.daf import Daf, daf_to_prompt
from app.domain.questions import MemberQuestionTree, QuestionNode
from app.logging_setup import get_logger, new_id
from app.providers.llm import ChatMessage, chat_model

# Broadcast topic the browser subscribes to for board state.
STATE_TOPIC = "board.state"
TRANSCRIPT_TOPIC = "board.transcript"


class _ExchangeVerdict(BaseModel):
    """How one answer landed, judged while it is fresh."""

    verdict: Literal[
        "answered", "evasive", "bluffed", "admitted_ignorance", "non_answer"
    ]
    note: str = Field(default="", max_length=300)


class TurnDecision(BaseModel):
    """What the member does next, decided in one fast call."""

    # WAIT lets the board say nothing. Turn detection is probabilistic: when it
    # fires on a mid-thought pause, speaking is the wrong move — a real member
    # lets the silence sit and the candidate carries on.
    signal: Literal["FOLLOWUP", "PROBE_HARDER", "DONE", "WAIT"]
    # Spoken verbatim. The tree supplies the substance; this supplies the wording.
    # Empty when the signal is WAIT.
    utterance: str = Field(default="", max_length=260)


@dataclass(slots=True)
class TreeCursor:
    """Position within one member's prepared questions."""

    tree: MemberQuestionTree
    node_index: int = 0
    follow_up_index: int = -1  # -1 means the seed has not been asked yet

    @property
    def node(self) -> QuestionNode | None:
        if self.node_index >= len(self.tree.nodes):
            return None
        return self.tree.nodes[self.node_index]

    def prepared_next(self) -> str | None:
        """The next prepared line, or None when this member is out of material."""
        node = self.node
        if node is None:
            return None
        if self.follow_up_index < 0:
            return node.seed
        if self.follow_up_index < len(node.follow_ups):
            return node.follow_ups[self.follow_up_index].text
        return None

    def probes(self) -> str:
        node = self.node
        if node is None or self.follow_up_index < 0:
            return "opening the thread"
        if self.follow_up_index < len(node.follow_ups):
            return node.follow_ups[self.follow_up_index].probes
        return "closing the thread"

    def descend(self) -> None:
        """Move one rung deeper, rolling to the next seed when exhausted."""
        node = self.node
        if node is None:
            return
        self.follow_up_index += 1
        if self.follow_up_index >= len(node.follow_ups):
            self.node_index += 1
            self.follow_up_index = -1

    def exhausted(self) -> bool:
        return self.node is None


def _tts_for(member_id: MemberId) -> elevenlabs.TTS:
    """That member's voice, with their own expressiveness settings."""
    settings = get_settings()
    voice = get_member(member_id).voice.elevenlabs

    return elevenlabs.TTS(
        voice_id=voice.voice_id,
        api_key=settings.elevenlabs_api_key,
        # Flash is the low-latency model; the quality loss is inaudible on a call.
        model="eleven_flash_v2_5",
        voice_settings=elevenlabs.VoiceSettings(
            stability=voice.stability,
            similarity_boost=0.75,
            style=voice.style,
            speed=voice.speed,
            use_speaker_boost=True,
        ),
    )


class BoardMemberAgent(Agent):
    """One member of the board, with their own voice and their own brief."""

    def __init__(self, member_id: MemberId, daf: Daf) -> None:
        member = get_member(member_id)
        super().__init__(
            instructions=f"{BOARD_CONDUCT}\n\nYou are {member.name}, "
            f"{member.title}.\n{member.persona}",
            tts=_tts_for(member_id),
        )
        self.member_id = member_id
        self.member = member
        self._daf = daf


# Fillers bought at zero cost: the member reacts the instant the candidate
# stops, while the real reply is still being generated. This is what humans do,
# and it hides ~500ms of latency.
_FILLERS = ("Hmm.", "I see.", "Right.", "Mm-hm.", "Yes.")


@dataclass
class BoardOrchestrator:
    """Drives the Conductor and executes its effects against the live session."""

    session: AgentSession
    room: rtc.Room
    daf: Daf
    agents: dict[MemberId, BoardMemberAgent]
    cursors: dict[MemberId, TreeCursor]
    session_id: str = field(default_factory=lambda: new_id("ses"))
    api_base: str = "http://127.0.0.1:8000"
    state: ConductorState = field(default_factory=initial_state)
    turn_index: int = 0
    _started_wall_ms: float = field(default_factory=lambda: time.monotonic() * 1000)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self.log = get_logger(component="board", session_id=self.session_id)

    # --- clock -------------------------------------------------------------

    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000 - self._started_wall_ms)

    # --- broadcast ---------------------------------------------------------

    async def _publish(self, topic: str, payload: dict) -> None:
        """Push state to the browser so the room UI can render it."""
        try:
            await self.room.local_participant.publish_data(
                json.dumps(payload).encode(), topic=topic, reliable=True
            )
        except Exception as exc:  # a dead data channel must not stop the interview
            self.log.warning("could not publish state", topic=topic, error=str(exc))

    async def _broadcast_state(self) -> None:
        await self._publish(
            STATE_TOPIC,
            {
                "phase": self.state.phase,
                "mic_holder": self.state.mic_holder,
                "elapsed_ms": self._now_ms(),
                "questions_in_block": self.state.questions_in_block,
                "completed_blocks": list(self.state.completed_blocks),
                "pending_members": list(self.state.pending_members),
                "ended_reason": self.state.ended_reason,
            },
        )

    async def _broadcast_utterance(self, speaker: str, text: str, member_id: str | None) -> None:
        at_ms = self._now_ms()
        await self._publish(
            TRANSCRIPT_TOPIC,
            {
                "speaker": speaker,
                "member_id": member_id,
                "text": text,
                "at_ms": at_ms,
                "turn": self.turn_index,
            },
        )
        # Persist as we go: a worker crash should cost the tail of the
        # transcript, not the evidence the evaluators need.
        await self._record(speaker, text, member_id, at_ms)

    async def _record(self, speaker: str, text: str, member_id: str | None, at_ms: int) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.api_base}/api/session/{self.session_id}/transcript",
                    json={
                        "speaker": speaker,
                        "member_id": member_id,
                        "text": text,
                        "at_ms": at_ms,
                    },
                )
        except Exception as exc:
            self.log.warning("could not persist utterance", error=str(exc))

    async def _capture_exchange(
        self, member_id: MemberId, question: str, prepared: str | None
    ) -> None:
        """Judge one question-and-answer and bank it.

        Runs as a background task on the cold tier, so it never touches the
        turn budget. Scoring stays a batch pass at the end — it simply reads
        these rows instead of re-deriving every judgement from the transcript,
        which also means a failed final evaluation no longer loses the signal.
        """
        answer = self._last_candidate_answer()
        if answer in ("(nothing yet)", "(silence)"):
            return

        log = self.log.bind(member_id=member_id, turn=self.turn_index)
        verdict, note = "answered", ""

        try:
            judged, _ = await chat_model(
                log,
                "digest",
                [
                    ChatMessage(
                        "system",
                        "Judge one exchange from a UPSC interview. Return JSON:\n"
                        '{"verdict": "answered"|"evasive"|"bluffed"|'
                        '"admitted_ignorance"|"non_answer", "note": str}\n\n'
                        "answered — addressed the question with real content.\n"
                        "evasive — spoke, but avoided what was asked.\n"
                        "bluffed — asserted something they plainly did not know.\n"
                        "admitted_ignorance — said they did not know. POSITIVE.\n"
                        "non_answer — 'yeah', 'okay', silence, nothing at all.\n\n"
                        "The note is one short sentence for the scorecard.",
                    ),
                    ChatMessage(
                        "user", f"Question: {question}\nAnswer: {answer}"
                    ),
                ],
                _ExchangeVerdict,
                temperature=0.1,
                max_tokens=200,
            )
            verdict, note = judged.verdict, judged.note
        except Exception as exc:
            # A missed judgement is not worth losing the pair over.
            log.warning("could not judge the exchange", error=str(exc))

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(
                    f"{self.api_base}/api/session/{self.session_id}/exchange",
                    json={
                        "turn": self.turn_index,
                        "member_id": member_id,
                        "question": question,
                        "answer": answer,
                        "verdict": verdict,
                        "note": note,
                    },
                )
        except Exception as exc:
            log.warning("could not bank the exchange", error=str(exc))

        log.info(f"exchange judged: {verdict}", verdict=verdict)

    async def _mark_ended(self, reason: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.api_base}/api/session/{self.session_id}/end",
                    params={"reason": reason},
                )
        except Exception as exc:
            self.log.warning("could not mark session ended", error=str(exc))

    # --- speaking ----------------------------------------------------------

    async def _decide_and_speak(self, member_id: MemberId, intent: SpeakIntent) -> None:
        """Produce and speak one utterance for the member holding the mic."""
        member = get_member(member_id)
        cursor = self.cursors.get(member_id)
        log = self.log.bind(member_id=member_id, intent=intent, turn=self.turn_index)

        # Handovers and the interruption are fixed beats — no LLM needed, which
        # keeps them instant.
        scripted = self._scripted(member_id, intent)
        if scripted is not None:
            await self.session.say(scripted, allow_interruptions=False)
            await self._broadcast_utterance(member.name, scripted, member_id)
            return

        prepared = cursor.prepared_next() if cursor else None
        if prepared is None:
            # Out of prepared material: hand back rather than improvise badly.
            log.info(f"{member.name} is out of prepared questions")
            await self._handle_signal("DONE")
            return

        history = self._recent_history()
        last_answer = self._last_candidate_answer()

        try:
            decision, _ = await chat_model(
                log,
                "hot",
                [
                    ChatMessage(
                        "system",
                        f"{BOARD_CONDUCT}\n\nYou are {member.name}, {member.title}.\n"
                        f"{member.persona}\n\n"
                        "You are mid-interview. RESPOND TO WHAT THE CANDIDATE JUST "
                        "SAID. You are not working through a list.\n\n"
                        "Judge their last answer first:\n\n"
                        "1. NON-ANSWER — ONLY when the reply carries no content "
                        "at all: 'yeah', 'okay', 'pardon', 'hmm', silence, or "
                        "profanity. Do NOT move on. Say so plainly and put the "
                        "SAME question again: 'That is not an answer. I asked "
                        "you...' Signal PROBE_HARDER.\n"
                        "   If the reply states ANY fact about themselves — a "
                        "place, a degree, a job, a number of attempts — it IS an "
                        "answer. Treat it under 4, never under 1. Calling a real "
                        "answer a non-answer is the worst mistake you can make.\n"
                        "2. EVASIVE OR VAGUE — they spoke but said nothing. Press on "
                        "the same point: 'You have not told me anything. Be "
                        "specific.' Signal PROBE_HARDER.\n"
                        "3. A CLAIM YOU DOUBT — challenge it: 'Are you certain?' "
                        "Signal PROBE_HARDER.\n"
                        "4. A REAL ANSWER THAT OPENS SOMETHING — follow THEIR "
                        "words, not your prepared line. Quote them back: 'You said "
                        "X — why?' Signal FOLLOWUP.\n"
                        "5. A REAL ANSWER, THREAD FINISHED — only now use the "
                        "prepared question below. Signal FOLLOWUP.\n"
                        "6. THEY ARE STILL THINKING — the reply trails off, ends "
                        "mid-thought ('I would say that... the main issue is'), or "
                        "is a filler like 'um' while they gather the sentence. Say "
                        "NOTHING. Signal WAIT with an empty utterance. A real "
                        "member lets the silence sit rather than talking over "
                        "someone who has not finished.\n\n"
                        "The prepared question is material to fall back on, NOT a "
                        "script. A board that ignores the answer and reads the next "
                        "item is not a board.\n\n"
                        'Return JSON: {"signal": "FOLLOWUP"|"PROBE_HARDER"|"DONE", '
                        '"utterance": str}',
                    ),
                    ChatMessage(
                        "user",
                        f"Candidate: {self.daf.full_name}\n\n"
                        f"Recent exchange:\n{history}\n\n"
                        f"THEIR LAST ANSWER: \"{last_answer}\"\n\n"
                        f"Prepared question, if the thread is finished: {prepared}\n"
                        f"What it measures: {cursor.probes() if cursor else ''}\n\n"
                        "Judge their answer, then speak.",
                    ),
                ],
                TurnDecision,
                temperature=0.7,
                # Headroom: a truncated response returns no JSON at all.
                max_tokens=400,
            )
        except Exception as exc:
            # Never leave dead air: fall back to the prepared line verbatim.
            log.error("hot LLM failed — speaking the prepared line", error=str(exc))
            decision = TurnDecision(signal="FOLLOWUP", utterance=prepared)

        if decision.signal == "WAIT" or not decision.utterance.strip():
            log.info(f"{member.name} waits — the candidate is still speaking")
            return

        await self.session.say(decision.utterance)
        await self._broadcast_utterance(member.name, decision.utterance, member_id)

        # Bank the exchange while it is fresh. Scoring stays a batch pass, but
        # it reads these rows rather than re-deriving everything at the end.
        asyncio.create_task(
            self._capture_exchange(member_id, decision.utterance, prepared)
        )

        # Only descend when the prepared question was actually used. Pressing
        # on a non-answer must re-ask, not consume the next item.
        if cursor and decision.signal == "FOLLOWUP":
            cursor.descend()

        if decision.signal == "DONE":
            await self._handle_signal("DONE")

    def _scripted(self, member_id: MemberId, intent: SpeakIntent) -> str | None:
        """Fixed beats that must not cost an LLM round-trip."""
        member = get_member(member_id)

        if intent == "opening":
            # A real board opens on the candidate, not on a topic. Everything
            # after this is a follow-up to how they introduce themselves.
            return (
                "Please, come in. Have a seat. "
                f"So — {self.daf.full_name}. Tell us about yourself."
            )
        if intent == "handover_out":
            return "That is all from my side."
        if intent == "handover_in":
            nxt = self.state.mic_holder
            name = get_member(nxt).name if nxt else "the next member"
            return f"Thank you. {name}, would you like to come in?"
        if intent == "interrupt":
            return "Yes — yes, I take your point, but let me stop you there."
        if intent == "closing":
            return (
                "Right. I think we have taken enough of your time. "
                "Thank you, your interview is over. You may go."
            )
        if intent == "seed" and member.id != "M0":
            return None
        return None

    def _last_candidate_answer(self) -> str:
        """What they just said, verbatim. The turn is a response to this."""
        for item in reversed(list(self.session.history.items)):
            if getattr(item, "role", None) == "user":
                return (getattr(item, "text_content", None) or "").strip() or "(silence)"
        return "(nothing yet)"

    def _recent_history(self, turns: int = 6) -> str:
        items = list(self.session.history.items)[-turns:]
        lines: list[str] = []
        for item in items:
            role = getattr(item, "role", None)
            content = getattr(item, "text_content", None) or ""
            if not content:
                continue
            who = "Candidate" if role == "user" else "Board"
            lines.append(f"{who}: {content}")
        return "\n".join(lines) or "(nothing yet)"

    # --- conductor ---------------------------------------------------------

    async def _apply(self, effects: list[Effect]) -> None:
        for effect in effects:
            match effect:
                case GrantMic():
                    agent = self.agents.get(effect.to)
                    if agent is not None:
                        self.session.update_agent(agent)
                        self.log.info(
                            f"mic granted to {get_member(effect.to).name}",
                            member_id=effect.to,
                            reason=effect.reason,
                        )
                case Speak():
                    await self._decide_and_speak(effect.member_id, effect.intent)
                case End():
                    self.log.info(f"interview ended: {effect.reason}", reason=effect.reason)
                    await self._mark_ended(effect.reason)
                    await self._broadcast_state()

        await self._broadcast_state()

    async def _dispatch(self, event) -> None:
        """Advance the Conductor, then act on what it decided.

        The lock covers only the state transition. Applying an effect can make
        a member signal DONE, which dispatches again — and asyncio.Lock is not
        reentrant, so holding it across `_apply` deadlocked the turn loop and
        left the mic stuck with whoever had it.
        """
        async with self._lock:
            transition = reduce(self.state, event, DEFAULT_CONFIG)
            self.state = transition.state
            # If this ever trips, two members are about to speak at once. Better
            # to fail loudly than ship the overlap to the candidate.
            assert_invariants(self.state)

        await self._apply(transition.effects)

    async def _handle_signal(self, signal: str) -> None:
        await self._dispatch(MemberSignalEvent(signal=signal, at_ms=self._now_ms()))  # type: ignore[arg-type]

    # --- lifecycle ---------------------------------------------------------

    async def begin(self) -> None:
        self.log.info(
            "board convened",
            candidate=self.daf.full_name,
            members=[m.id for m in BOARD],
            prepared=[m for m, c in self.cursors.items() if not c.exhausted()],
        )
        await self._dispatch(Start(at_ms=self._now_ms()))

    async def on_candidate_turn(self, transcript: str) -> None:
        """Called when the candidate finishes speaking."""
        self.turn_index += 1
        words = len(transcript.split())

        self.log.info(
            f"candidate answered ({words} words)",
            turn=self.turn_index,
            words=words,
            mic_holder=self.state.mic_holder,
        )
        await self._broadcast_utterance("You", transcript, None)

        # Rambling gets cut off mid-thought, exactly as a real board would.
        await self._dispatch(AspirantSpoke(at_ms=self._now_ms(), word_count=words))
        if self.state.phase == "ended":
            return

        await self._handle_signal("FOLLOWUP")

    async def tick(self) -> None:
        await self._dispatch(Tick(at_ms=self._now_ms()))

    async def abandon(self, reason: str) -> None:
        """End the interview because the candidate left, not because it finished."""
        self.log.info(f"interview abandoned: {reason}", reason=reason)
        await self._dispatch(Abort(reason=reason, at_ms=self._now_ms()))

    @property
    def ended(self) -> bool:
        return self.state.phase == "ended"


def build_agents(daf: Daf) -> dict[MemberId, BoardMemberAgent]:
    return {m.id: BoardMemberAgent(m.id, daf) for m in BOARD}


def build_cursors(trees: list[MemberQuestionTree]) -> dict[MemberId, TreeCursor]:
    return {t.member_id: TreeCursor(tree=t) for t in trees}


def system_context(daf: Daf) -> str:
    """Full DAF, for the Chairman's framing questions and the evaluators."""
    return daf_to_prompt(daf)
