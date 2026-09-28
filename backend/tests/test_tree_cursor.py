"""The tree cursor.

This is what makes a live turn cheap: the member walks prepared material and
the LLM only rephrases it. If the cursor drifts — repeats a rung, skips a
seed, or runs off the end without saying so — the interview either loops or
falls silent, so its walk is pinned exactly.
"""

from __future__ import annotations

import pytest

from agent.board_agent import TreeCursor
from app.domain.questions import FollowUp, MemberQuestionTree, QuestionNode


def node(seed: str, *follow_ups: str) -> QuestionNode:
    return QuestionNode(
        seed=seed,
        section="home_state",
        follow_ups=[FollowUp(text=t, probes=f"probing {t}") for t in follow_ups],
    )


def cursor(*nodes: QuestionNode) -> TreeCursor:
    return TreeCursor(
        tree=MemberQuestionTree(member_id="M2", member_name="Shri Rathore", nodes=list(nodes))
    )


class TestWalk:
    def test_starts_on_the_seed(self):
        c = cursor(node("What failed in Jhansi?", "Whose failure?", "You are the DM. Now what?"))
        assert c.prepared_next() == "What failed in Jhansi?"

    def test_descends_through_follow_ups_in_order(self):
        c = cursor(node("Seed", "Rung one", "Rung two", "Rung three"))

        seen = []
        for _ in range(4):
            seen.append(c.prepared_next())
            c.descend()

        assert seen == ["Seed", "Rung one", "Rung two", "Rung three"]

    def test_never_repeats_a_rung(self):
        c = cursor(node("Seed", "A", "B"))

        seen = []
        while not c.exhausted():
            line = c.prepared_next()
            if line is None:
                break
            seen.append(line)
            c.descend()

        assert len(seen) == len(set(seen)), f"repeated a question: {seen}"

    def test_rolls_on_to_the_next_seed_when_a_thread_is_spent(self):
        c = cursor(node("First seed", "A"), node("Second seed", "B"))

        assert c.prepared_next() == "First seed"
        c.descend()
        assert c.prepared_next() == "A"
        c.descend()
        # Thread one is spent — the next line must be the second seed.
        assert c.prepared_next() == "Second seed"

    def test_reports_exhaustion_rather_than_looping(self):
        c = cursor(node("Only seed", "Only rung"))

        c.descend()
        c.descend()

        assert c.exhausted() is True
        assert c.prepared_next() is None

    def test_surfaces_what_each_rung_measures(self):
        c = cursor(node("Seed", "Whose failure?"))

        assert c.probes() == "opening the thread"
        c.descend()
        assert c.probes() == "probing Whose failure?"


class TestExhaustedTree:
    def test_an_empty_walk_is_immediately_exhausted(self):
        c = cursor(node("Seed", "A"))
        c.node_index = 99
        assert c.exhausted() is True
        assert c.prepared_next() is None

    def test_descending_past_the_end_is_harmless(self):
        c = cursor(node("Seed", "A"))
        for _ in range(20):
            c.descend()
        assert c.exhausted() is True


class TestAgainstRealTreeShape:
    @pytest.mark.parametrize("follow_ups", [1, 4, 6])
    def test_walks_every_rung_exactly_once(self, follow_ups: int):
        c = cursor(node("Seed", *[f"Rung {i}" for i in range(follow_ups)]))

        walked = 0
        while c.prepared_next() is not None:
            walked += 1
            c.descend()

        # Seed plus each follow-up.
        assert walked == follow_ups + 1
