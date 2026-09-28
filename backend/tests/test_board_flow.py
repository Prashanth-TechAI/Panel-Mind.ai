"""A whole interview, end to end through the orchestrator.

The live e2e proves the Chairman opens. This proves the rest: that the mic
actually travels to all four experts, that handovers are spoken aloud, that no
two members ever hold it at once, and that the interview closes.

The speech and network edges are stubbed; everything between them — the
Conductor, the tree cursors, the agent swap — is the real code.
"""

from __future__ import annotations

import pytest

from agent.board_agent import BoardOrchestrator, TreeCursor, build_agents
from app.domain.board import BOARD, CHAIRMAN_ID, QUESTIONING_ORDER
from app.domain.daf import Daf
from app.domain.questions import FollowUp, MemberQuestionTree, QuestionNode

DAF = Daf.model_validate(
    {
        "full_name": "Rohit Sharma",
        "home_state": "Uttar Pradesh",
        "home_district": "Jhansi",
        "education": {
            "graduation_subject": "Mechanical Engineering",
            "graduation_college": "IIT Kanpur",
        },
        "optional_subject": "Sociology",
        "hobbies": ["Reading historical fiction"],
        "service_preference": ["IAS"],
    }
)


class FakeHistory:
    items: list = []


class FakeSession:
    """Stands in for the LiveKit AgentSession."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.agent_swaps: list[str] = []
        self.history = FakeHistory()

    async def say(self, text: str, **_kwargs) -> None:
        self.spoken.append(text)

    def update_agent(self, agent) -> None:
        self.agent_swaps.append(agent.member_id)


class FakeParticipant:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    async def publish_data(self, payload: bytes, *, topic: str, **_kw) -> None:
        self.published.append((topic, payload))


class FakeRoom:
    def __init__(self) -> None:
        self.local_participant = FakeParticipant()


def tree_for(member_id: str) -> MemberQuestionTree:
    """Three seeds, four rungs each — the real generated shape."""
    return MemberQuestionTree(
        member_id=member_id,  # type: ignore[arg-type]
        member_name=member_id,
        nodes=[
            QuestionNode(
                seed=f"{member_id} seed {n}",
                section="identity" if member_id == "M0" else "home_state",
                follow_ups=[
                    FollowUp(text=f"{member_id} s{n} rung {r}", probes="depth")
                    for r in range(4)
                ],
            )
            for n in range(3)
        ],
    )


@pytest.fixture
def board(monkeypatch):
    session, room = FakeSession(), FakeRoom()

    orchestrator = BoardOrchestrator(
        session=session,  # type: ignore[arg-type]
        room=room,  # type: ignore[arg-type]
        daf=DAF,
        agents=build_agents(DAF),
        cursors={m.id: TreeCursor(tree=tree_for(m.id)) for m in BOARD},
    )

    # The hot LLM only rephrases a prepared question; the flow does not depend
    # on its wording, so stub it and keep the test offline and fast.
    async def fake_decide(member_id, intent):
        member_name = member_id
        cursor = orchestrator.cursors.get(member_id)
        scripted = orchestrator._scripted(member_id, intent)
        line = scripted if scripted is not None else (cursor.prepared_next() if cursor else None)
        if line is None:
            await orchestrator._handle_signal("DONE")
            return
        await session.say(line)
        await orchestrator._broadcast_utterance(member_name, line, member_id)
        if cursor and scripted is None:
            cursor.descend()

    monkeypatch.setattr(orchestrator, "_decide_and_speak", fake_decide)
    # No control plane in this test.
    monkeypatch.setattr(orchestrator, "_record", lambda *a, **k: _noop())
    monkeypatch.setattr(orchestrator, "_mark_ended", lambda *a, **k: _noop())

    return orchestrator, session, room


async def _noop() -> None:
    return None


class TestWholeInterview:
    async def test_the_mic_reaches_every_member_in_order(self, board):
        orchestrator, session, _ = board
        await orchestrator.begin()

        # Answer until the board runs its course.
        for turn in range(200):
            if orchestrator.ended:
                break
            await orchestrator.on_candidate_turn(f"Answer number {turn}, sir.")
            await orchestrator.tick()

        assert orchestrator.ended, "the interview never closed"
        assert orchestrator.state.completed_blocks == (CHAIRMAN_ID, *QUESTIONING_ORDER), (
            "the mic did not reach every member in the Chairman's calling order"
        )

    async def test_every_member_actually_speaks(self, board):
        orchestrator, session, _ = board
        await orchestrator.begin()

        for turn in range(200):
            if orchestrator.ended:
                break
            await orchestrator.on_candidate_turn(f"Answer {turn}, sir.")

        swapped = set(session.agent_swaps)
        assert swapped == {m.id for m in BOARD}, (
            f"these members were never given the floor: "
            f"{ {m.id for m in BOARD} - swapped }"
        )

    async def test_handovers_are_spoken_aloud(self, board):
        orchestrator, session, _ = board
        await orchestrator.begin()

        for turn in range(200):
            if orchestrator.ended:
                break
            await orchestrator.on_candidate_turn(f"Answer {turn}, sir.")

        said = " ".join(session.spoken)
        assert "That is all from my side." in said, "no member ever signed off"
        assert "would you like to come in?" in said, "the Chairman never called anyone in"
        assert "your interview is over" in said.lower(), "the Chairman never closed"

    async def test_only_one_member_ever_holds_the_mic(self, board):
        orchestrator, _, _ = board
        await orchestrator.begin()

        holders: list[str | None] = []
        for turn in range(200):
            if orchestrator.ended:
                break
            await orchestrator.on_candidate_turn(f"Answer {turn}, sir.")
            holders.append(orchestrator.state.mic_holder)

        # assert_invariants runs inside every dispatch; reaching here means it
        # never tripped. Confirm the holder was always a single, known member.
        valid = {m.id for m in BOARD}
        assert all(h is None or h in valid for h in holders)

    async def test_a_rambling_answer_is_interrupted(self, board):
        orchestrator, session, _ = board
        await orchestrator.begin()
        before = len(session.spoken)

        await orchestrator.on_candidate_turn(" ".join(["word"] * 250))

        assert len(session.spoken) > before, "the board sat silent through a ramble"
        assert any("stop you there" in line for line in session.spoken), (
            "the board never interrupted a 250-word answer"
        )

    async def test_the_room_is_kept_informed_throughout(self, board):
        orchestrator, _, room = board
        await orchestrator.begin()

        for turn in range(40):
            if orchestrator.ended:
                break
            await orchestrator.on_candidate_turn(f"Answer {turn}, sir.")

        topics = {topic for topic, _ in room.local_participant.published}
        assert "board.state" in topics, "the UI was never told who holds the mic"
        assert "board.transcript" in topics, "the UI was never sent the transcript"

    async def test_a_candidate_walking_out_ends_it(self, board):
        orchestrator, _, _ = board
        await orchestrator.begin()
        await orchestrator.on_candidate_turn("Sir, I have to leave.")

        await orchestrator.abandon("candidate_left")

        assert orchestrator.ended
        assert orchestrator.state.ended_reason == "candidate_left"
