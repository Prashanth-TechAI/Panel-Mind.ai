"""Question-tree generation.

The offline tests pin prompt construction — above all, that a member is never
handed material outside their own portfolio, since that is what stops five
members converging on the same three questions.

The ``live`` test actually calls the model. It is the only proof that the
prompt yields usable questions, so it is worth its cost: run with
``pytest -m live``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.board import get_member
from app.domain.daf import Daf, to_portfolios
from app.domain.questions import (
    FOLLOW_UPS_PER_SEED,
    SEEDS_PER_MEMBER,
    FollowUp,
    MemberQuestionTree,
    QuestionNode,
    build_prompt,
    generate_all_trees,
)

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
        "hobbies": ["Reading historical fiction", "Long-distance running"],
        "service_preference": ["IAS", "IPS"],
        "work_experience": ["Two years at ISRO, propulsion division"],
        "positions_of_responsibility": ["NSS unit secretary"],
        "attempt_number": 2,
    }
)


def portfolio_for(member_id: str):
    return next(p for p in to_portfolios(DAF) if p.member_id == member_id)


class TestPromptConstruction:
    def test_carries_the_members_own_portfolio(self):
        messages = build_prompt(portfolio_for("M1"), DAF)
        user = messages[1].content

        assert "Sociology" in user
        assert "Mechanical Engineering" in user

    def test_withholds_material_the_member_does_not_own(self):
        """The subject expert must not see hobbies, or both members ask about them."""
        user = build_prompt(portfolio_for("M1"), DAF)[1].content

        assert "running" not in user.lower()
        assert "historical fiction" not in user.lower()

    def test_names_only_the_sections_the_member_may_question_on(self):
        system = build_prompt(portfolio_for("M2"), DAF)[0].content

        for section in get_member("M2").owns:
            assert section in system
        # M2 is the ex-bureaucrat; the optional subject belongs to M1.
        assert "optional_subject" not in system

    def test_carries_the_conduct_rules_including_the_praise_ban(self):
        system = build_prompt(portfolio_for("M0"), DAF)[0].content

        assert "NEVER praise" in system
        assert "under 25 words" in system.lower()

    def test_states_the_required_tree_shape(self):
        system = build_prompt(portfolio_for("M3"), DAF)[0].content

        assert str(SEEDS_PER_MEMBER) in system
        assert str(FOLLOW_UPS_PER_SEED) in system
        assert "DESCEND" in system

    def test_identifies_the_candidate_without_leaking_the_whole_daf(self):
        user = build_prompt(portfolio_for("M4"), DAF)[1].content

        assert "Rohit Sharma" in user
        # The psychologist owns hobbies, sports and languages — the district
        # appears only as context for the dialect question, never education.
        assert "Sociology" not in user
        assert "IIT Kanpur" not in user

    @pytest.mark.parametrize("member_id", ["M0", "M1", "M2", "M3", "M4"])
    def test_every_member_gets_a_usable_prompt(self, member_id):
        messages = build_prompt(portfolio_for(member_id), DAF)

        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert len(messages[1].content) > 60, "portfolio rendered empty"


class TestSchema:
    def test_rejects_a_seed_with_no_follow_ups(self):
        with pytest.raises(ValidationError):
            QuestionNode(seed="Why civil services?", section="identity", follow_ups=[])

    def test_rejects_a_tree_with_no_nodes(self):
        with pytest.raises(ValidationError):
            MemberQuestionTree(member_id="M0", member_name="Chairman", nodes=[])

    def test_accepts_a_well_formed_tree(self):
        tree = MemberQuestionTree(
            member_id="M2",
            member_name="Shri Rathore",
            nodes=[
                QuestionNode(
                    seed="What is the biggest administrative failure in Jhansi?",
                    section="home_state",
                    follow_ups=[
                        FollowUp(text="Whose failure was it?", probes="assigning responsibility"),
                    ],
                )
            ],
        )
        assert tree.nodes[0].follow_ups[0].probes


@pytest.mark.live
class TestLiveGeneration:
    async def test_prepares_real_questions_for_every_member(self):
        trees, failures = await generate_all_trees(DAF)

        assert not failures, f"members failed to prepare: {failures}"
        assert len(trees) == 5

        for tree in trees:
            owned = set(get_member(tree.member_id).owns)

            assert tree.nodes, f"{tree.member_name} produced no seeds"
            for node in tree.nodes:
                assert node.section in owned, (
                    f"{tree.member_name} asked outside portfolio: {node.section}"
                )
                assert node.follow_ups, f"{tree.member_name} seed has no descent"
                # Boards are terse. A 60-word question is a written question.
                assert len(node.seed.split()) < 60, f"seed too long: {node.seed}"

    async def test_questions_are_drawn_from_the_candidates_own_form(self):
        trees, _ = await generate_all_trees(DAF)

        academic = next(t for t in trees if t.member_id == "M1")
        text = " ".join(
            [n.seed for n in academic.nodes]
            + [f.text for n in academic.nodes for f in n.follow_ups]
        ).lower()

        # The subject expert owns education and the optional subject; at least
        # one of them must actually appear, or the questions are generic.
        assert "sociology" in text or "mechanical" in text or "engineering" in text

    async def test_the_board_does_not_praise(self):
        trees, _ = await generate_all_trees(DAF)

        everything = " ".join(
            [n.seed for t in trees for n in t.nodes]
            + [f.text for t in trees for n in t.nodes for f in n.follow_ups]
        ).lower()

        for praise in ("great answer", "excellent", "well said", "good point"):
            assert praise not in everything, f"board praised the candidate: {praise!r}"
