"""The evaluation plane.

Signal extraction is arithmetic, so it is pinned exactly — those numbers are
handed to the evaluators as fact, and a wrong one silently skews five
scorecards. Prompt construction is pinned for the two things that matter most:
that each evaluator is weighted toward its own member's traits, and that
admitting ignorance is rewarded rather than punished.
"""

from __future__ import annotations

import pytest

from app.domain.board import BOARD, TRAIT_LABELS, UPSC_TRAITS
from app.domain.daf import Daf
from app.domain.evaluation import (
    MAX_MARKS,
    AnswerFlag,
    MemberScorecard,
    TraitScore,
    Utterance,
    average_traits,
    build_evaluator_prompt,
    extract_signals,
    render_transcript,
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
        "hobbies": ["Reading historical fiction"],
        "service_preference": ["IAS"],
    }
)


def answer(text: str, at_ms: int = 0) -> Utterance:
    return Utterance(speaker="You", member_id=None, text=text, at_ms=at_ms)


def question(text: str, member_id: str = "M0", at_ms: int = 0) -> Utterance:
    return Utterance(speaker="Chairman", member_id=member_id, text=text, at_ms=at_ms)


class TestSignalExtraction:
    def test_counts_only_the_candidates_answers(self):
        signals = extract_signals(
            [question("Why civil services?"), answer("Because I want to serve."), question("Hmm.")]
        )

        assert signals.answers == 1
        assert signals.total_words == 5

    def test_measures_answer_length(self):
        signals = extract_signals([answer("one two three"), answer("one two three four five")])

        assert signals.average_words_per_answer == 4.0
        assert signals.longest_answer_words == 5

    def test_detects_admitted_ignorance_in_its_several_forms(self):
        signals = extract_signals(
            [
                answer("I don't know, sir."),
                answer("I do not know that."),
                answer("I am not sure about the figure."),
                answer("The capital is Lucknow."),
            ]
        )

        assert signals.admitted_ignorance_count == 3

    def test_counts_filler_words(self):
        signals = extract_signals([answer("So basically I mean it is actually like that")])

        assert signals.filler_ratio > 0
        assert signals.total_words == 9

    def test_does_not_count_fillers_inside_longer_words(self):
        # "like" must not match inside "likely", or the ratio inflates.
        signals = extract_signals([answer("It is likely alike unlikely")])

        assert signals.filler_ratio == 0.0

    def test_counts_an_over_long_answer_as_an_interruption(self):
        signals = extract_signals([answer(" ".join(["word"] * 200)), answer("Short.")])

        assert signals.interruptions_taken == 1

    def test_an_empty_interview_yields_zeroes_not_a_crash(self):
        signals = extract_signals([])

        assert signals.answers == 0
        assert signals.average_words_per_answer == 0.0
        assert signals.filler_ratio == 0.0


class TestTranscriptRendering:
    def test_labels_the_candidate_distinctly_from_the_board(self):
        rendered = render_transcript(
            [question("Tell us about Jhansi.", at_ms=5_000), answer("It is in Bundelkhand.", 9_000)]
        )

        assert "CHAIRMAN: Tell us about Jhansi." in rendered
        assert "CANDIDATE: It is in Bundelkhand." in rendered
        assert "[5s]" in rendered and "[9s]" in rendered

    def test_says_so_when_nothing_was_recorded(self):
        assert "no exchanges" in render_transcript([])


class TestEvaluatorPrompt:
    @pytest.mark.parametrize("member", BOARD, ids=[m.id for m in BOARD])
    def test_every_evaluator_scores_all_seven_official_traits(self, member):
        system = build_evaluator_prompt(member.id, DAF, [answer("Yes.")], extract_signals([]))[0].content

        for trait in UPSC_TRAITS:
            assert trait in system, f"{member.name} not asked to score {trait}"

    @pytest.mark.parametrize("member", BOARD, ids=[m.id for m in BOARD])
    def test_each_evaluator_is_weighted_toward_its_own_members_priorities(self, member):
        system = build_evaluator_prompt(member.id, DAF, [], extract_signals([]))[0].content

        weighted = system.split("You weigh these most heavily:")[1].split("\n")[0]
        for trait in member.weighs:
            assert TRAIT_LABELS[trait] in weighted

    def test_treats_admitting_ignorance_as_a_positive(self):
        system = build_evaluator_prompt("M1", DAF, [], extract_signals([]))[0].content

        assert "POSITIVE signal" in system
        assert "never penalise" in system

    def test_demands_bluffs_be_quoted(self):
        system = build_evaluator_prompt("M3", DAF, [], extract_signals([]))[0].content

        assert "bluff" in system
        assert "quote" in system.lower()

    def test_anchors_marks_to_real_reported_ranges(self):
        system = build_evaluator_prompt("M0", DAF, [], extract_signals([]))[0].content

        assert str(MAX_MARKS) in system
        assert "160 and 190" in system, "evaluators need calibration or they inflate"

    def test_hands_measured_signals_to_the_evaluator_as_fact(self):
        signals = extract_signals([answer("I don't know."), answer(" ".join(["w"] * 200))])
        user = build_evaluator_prompt("M2", DAF, [answer("x")], signals)[1].content

        assert "do not re-derive" in user
        assert "times they said" in user
        assert "interrupt" in user

    def test_gives_the_evaluator_the_whole_daf_not_one_portfolio(self):
        # Unlike questioning, scoring needs the full picture.
        user = build_evaluator_prompt("M1", DAF, [], extract_signals([]))[1].content

        assert "Jhansi" in user
        assert "Sociology" in user
        assert "historical fiction" in user


class TestTraitAveraging:
    def card(self, member_id: str, name: str, scores: dict[str, int]) -> MemberScorecard:
        return MemberScorecard(
            member_id=member_id,
            member_name=name,
            traits=[TraitScore(trait=t, score=s, note="n") for t, s in scores.items()],
            marks=170,
            remark="r",
        )

    def test_averages_each_trait_across_evaluators(self):
        cards = [
            self.card("M0", "Chairman", {"clear_exposition": 8, "moral_integrity": 6}),
            self.card("M1", "Prof. Iyer", {"clear_exposition": 4, "moral_integrity": 10}),
        ]

        averages = average_traits(cards)

        assert averages["clear_exposition"] == 6.0
        assert averages["moral_integrity"] == 8.0

    def test_reports_every_trait_even_when_nobody_scored_it(self):
        averages = average_traits([self.card("M0", "Chairman", {"mental_alertness": 7})])

        assert set(averages) == set(UPSC_TRAITS)
        assert averages["depth_of_interest"] == 0.0


class TestScorecardSchema:
    def test_rejects_marks_beyond_the_paper_total(self):
        with pytest.raises(Exception):
            MemberScorecard(
                member_id="M0",
                member_name="Chairman",
                traits=[TraitScore(trait="mental_alertness", score=5, note="n")],
                marks=MAX_MARKS + 1,
                remark="r",
            )

    def test_rejects_an_out_of_range_trait_score(self):
        with pytest.raises(Exception):
            TraitScore(trait="mental_alertness", score=11, note="n")

    def test_a_flag_carries_the_candidates_own_words(self):
        flag = AnswerFlag(
            kind="bluff",
            quote="NITI Aayog was set up in 2012.",
            comment="Wrong by three years, asserted confidently.",
        )
        assert flag.kind == "bluff"
        assert flag.quote
