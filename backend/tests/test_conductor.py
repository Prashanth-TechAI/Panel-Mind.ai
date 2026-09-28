"""The Conductor is the only thing standing between a realistic board and five
agents shouting over each other, so it is tested exhaustively — including a
full simulated interview that re-checks every invariant on every transition.
"""

from __future__ import annotations

import pytest

from app.domain.board import CHAIRMAN_ID, QUESTIONING_ORDER
from app.domain.conductor import (
    DEFAULT_CONFIG,
    Abort,
    AspirantSpoke,
    ConductorConfig,
    ConductorEvent,
    ConductorState,
    DigestUpdated,
    Effect,
    End,
    GrantMic,
    MemberSignalEvent,
    Speak,
    Start,
    Tick,
    assert_invariants,
    elapsed_ms,
    initial_state,
    reduce,
)

T0 = 1_000_000


def run(
    events: list[ConductorEvent],
    config: ConductorConfig = DEFAULT_CONFIG,
    start: ConductorState | None = None,
) -> tuple[ConductorState, list[Effect]]:
    """Apply a sequence of events, asserting invariants after each one."""
    state = start or initial_state()
    effects: list[Effect] = []

    for event in events:
        transition = reduce(state, event, config)
        state = transition.state
        assert_invariants(state)
        effects.extend(transition.effects)

    return state, effects


def speak_intents(effects: list[Effect]) -> list[str]:
    return [f"{e.member_id}:{e.intent}" for e in effects if isinstance(e, Speak)]


def grants(effects: list[Effect]) -> list[str]:
    return [e.to for e in effects if isinstance(e, GrantMic)]


class TestInitialState:
    def test_is_idle_with_nobody_holding_the_mic(self):
        state = initial_state()
        assert state.phase == "idle"
        assert state.mic_holder is None
        assert state.pending_members == QUESTIONING_ORDER
        assert_invariants(state)


class TestStarting:
    def test_gives_the_mic_to_the_chairman_and_opens(self):
        state, effects = run([Start(at_ms=T0)])

        assert state.phase == "chairman_opening"
        assert state.mic_holder == CHAIRMAN_ID
        assert state.questions_in_block == 1
        assert grants(effects) == [CHAIRMAN_ID]
        assert speak_intents(effects) == [f"{CHAIRMAN_ID}:opening"]

    def test_ignores_a_second_start(self):
        state, effects = run([Start(at_ms=T0), Start(at_ms=T0 + 5_000)])

        assert state.phase == "chairman_opening"
        assert grants(effects) == [CHAIRMAN_ID]


class TestFollowUps:
    def test_keeps_the_mic_with_the_same_member_and_counts_the_question(self):
        state, effects = run(
            [
                Start(at_ms=T0),
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 20_000),
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 40_000),
            ]
        )

        assert state.mic_holder == CHAIRMAN_ID
        assert state.questions_in_block == 3
        assert speak_intents(effects) == [
            f"{CHAIRMAN_ID}:opening",
            f"{CHAIRMAN_ID}:followup",
            f"{CHAIRMAN_ID}:followup",
        ]

    def test_distinguishes_probe_harder_from_an_ordinary_follow_up(self):
        _, effects = run(
            [Start(at_ms=T0), MemberSignalEvent(signal="PROBE_HARDER", at_ms=T0 + 20_000)]
        )

        assert f"{CHAIRMAN_ID}:probe_harder" in speak_intents(effects)


class TestHandover:
    def test_is_spoken_aloud_not_a_silent_cut(self):
        state, effects = run(
            [Start(at_ms=T0), MemberSignalEvent(signal="DONE", at_ms=T0 + 60_000)]
        )

        assert state.phase == "member_block"
        assert state.mic_holder == "M1"

        # Outgoing signs off, Chairman calls the next member in, that member opens.
        assert speak_intents(effects) == [
            f"{CHAIRMAN_ID}:opening",
            f"{CHAIRMAN_ID}:handover_out",
            f"{CHAIRMAN_ID}:handover_in",
            "M1:seed",
        ]

    def test_carries_the_digest_to_the_incoming_member(self):
        digest = "Strong on state schemes. Bluffed once on NITI Aayog."
        _, effects = run(
            [
                Start(at_ms=T0),
                DigestUpdated(digest=digest, at_ms=T0 + 30_000),
                MemberSignalEvent(signal="DONE", at_ms=T0 + 60_000),
            ]
        )

        grant = next(e for e in effects if isinstance(e, GrantMic) and e.to == "M1")
        assert grant.digest == digest

    def test_fires_when_the_question_limit_is_hit_even_without_a_done(self):
        config = ConductorConfig(max_questions_per_block=3)
        state, _ = run(
            [
                Start(at_ms=T0),
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 10_000),
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 20_000),
                # Block is now full; the next signal must move the mic on.
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 30_000),
            ],
            config,
        )

        assert state.mic_holder == "M1"
        assert state.completed_blocks == (CHAIRMAN_ID,)

    def test_fires_on_a_tick_when_the_block_runs_out_of_time(self):
        state, _ = run(
            [Start(at_ms=T0), Tick(at_ms=T0 + DEFAULT_CONFIG.chairman_opening_ms + 1)]
        )

        assert state.mic_holder == "M1"
        assert state.phase == "member_block"


class TestRambling:
    def test_is_interrupted_by_whoever_holds_the_mic(self):
        _, effects = run(
            [
                Start(at_ms=T0),
                AspirantSpoke(
                    at_ms=T0 + 30_000, word_count=DEFAULT_CONFIG.max_answer_words + 1
                ),
            ]
        )

        assert f"{CHAIRMAN_ID}:interrupt" in speak_intents(effects)

    def test_leaves_a_normal_length_answer_alone(self):
        _, effects = run(
            [Start(at_ms=T0), AspirantSpoke(at_ms=T0 + 30_000, word_count=60)]
        )

        assert speak_intents(effects) == [f"{CHAIRMAN_ID}:opening"]


class TestCompleteInterview:
    def test_gives_every_member_exactly_one_block_then_ends(self):
        state = initial_state()
        all_effects: list[Effect] = []
        now = T0

        def step(event: ConductorEvent) -> None:
            nonlocal state
            transition = reduce(state, event, DEFAULT_CONFIG)
            state = transition.state
            assert_invariants(state)
            all_effects.extend(transition.effects)

        step(Start(at_ms=now))

        # Chairman plus four members: each asks two follow-ups then hands over.
        for _ in range(5):
            now += 30_000
            step(MemberSignalEvent(signal="FOLLOWUP", at_ms=now))
            now += 30_000
            step(MemberSignalEvent(signal="FOLLOWUP", at_ms=now))
            now += 30_000
            step(MemberSignalEvent(signal="DONE", at_ms=now))

        assert state.phase == "chairman_closing"
        assert state.completed_blocks == (CHAIRMAN_ID, *QUESTIONING_ORDER)
        assert state.pending_members == ()

        now += 20_000
        step(MemberSignalEvent(signal="DONE", at_ms=now))

        assert state.phase == "ended"
        assert state.mic_holder is None
        assert state.ended_reason == "interview_complete"

        # Every member spoke, and the Chairman both opened and closed.
        spoke = {e.member_id for e in all_effects if isinstance(e, Speak)}
        assert spoke == {CHAIRMAN_ID, *QUESTIONING_ORDER}
        assert f"{CHAIRMAN_ID}:closing" in speak_intents(all_effects)

    def test_never_lets_two_members_hold_the_mic_at_once(self):
        state = reduce(initial_state(), Start(at_ms=T0), DEFAULT_CONFIG).state
        now = T0
        signals = ("FOLLOWUP", "PROBE_HARDER", "DONE")

        # Hammer the machine with a long mixed event stream.
        for i in range(200):
            if state.phase == "ended":
                break
            now += 7_000
            event: ConductorEvent = (
                Tick(at_ms=now)
                if i % 4 == 3
                else MemberSignalEvent(signal=signals[i % 3], at_ms=now)  # type: ignore[arg-type]
            )
            state = reduce(state, event, DEFAULT_CONFIG).state
            assert_invariants(state)

        assert state.phase == "ended"


class TestTimeBudget:
    def test_forces_the_chairman_to_close_once_the_total_budget_is_spent(self):
        state, _ = run([Start(at_ms=T0), Tick(at_ms=T0 + DEFAULT_CONFIG.total_budget_ms + 1)])

        assert state.phase == "chairman_closing"
        assert state.mic_holder == CHAIRMAN_ID
        assert state.pending_members == ()

    def test_ends_outright_if_the_closing_itself_overruns(self):
        state, _ = run(
            [
                Start(at_ms=T0),
                Tick(at_ms=T0 + DEFAULT_CONFIG.total_budget_ms + 1),
                Tick(
                    at_ms=T0
                    + DEFAULT_CONFIG.total_budget_ms
                    + DEFAULT_CONFIG.member_block_ms
                    + 2
                ),
            ]
        )

        assert state.phase == "ended"
        assert state.ended_reason == "closing_overran"

    def test_never_rewinds_the_clock_on_an_out_of_order_event(self):
        state, _ = run(
            [Start(at_ms=T0), Tick(at_ms=T0 + 60_000), Tick(at_ms=T0 + 10_000)]
        )

        assert elapsed_ms(state) == 60_000


class TestTerminalState:
    def test_ignores_every_event_after_the_interview_ends(self):
        state, effects = run(
            [
                Start(at_ms=T0),
                Abort(reason="candidate_left", at_ms=T0 + 5_000),
                MemberSignalEvent(signal="FOLLOWUP", at_ms=T0 + 10_000),
                Tick(at_ms=T0 + 999_000),
            ]
        )

        assert state.phase == "ended"
        assert state.ended_reason == "candidate_left"
        assert len([e for e in effects if isinstance(e, End)]) == 1


class TestInvariantAssertions:
    def test_catch_a_hand_corrupted_state(self):
        from dataclasses import replace

        broken = replace(initial_state(), phase="member_block", mic_holder=None)
        with pytest.raises(AssertionError, match="no mic holder"):
            assert_invariants(broken)

        doubled = replace(initial_state(), completed_blocks=("M1", "M1"))
        with pytest.raises(AssertionError, match="two blocks"):
            assert_invariants(doubled)
