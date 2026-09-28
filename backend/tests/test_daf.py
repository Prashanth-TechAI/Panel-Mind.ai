from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.board import BOARD, DAF_FIELDS, MEMBER_IDS
from app.domain.daf import (
    Daf,
    daf_to_prompt,
    portfolio_to_prompt,
    to_portfolios,
    to_sections,
)

VALID_DAF = {
    "full_name": "Rohit Sharma",
    "home_state": "Uttar Pradesh",
    "home_district": "Jhansi",
    "education": {
        "graduation_subject": "Mechanical Engineering",
        "graduation_college": "IIT Kanpur",
        "university": "IIT Kanpur",
    },
    "optional_subject": "Sociology",
    "hobbies": ["Reading historical fiction", "Long-distance running"],
    "service_preference": ["IAS", "IPS"],
    "attempt_number": 2,
}


def parse(**overrides) -> Daf:
    return Daf.model_validate({**VALID_DAF, **overrides})


class TestSchema:
    def test_accepts_a_realistic_form_and_fills_defaults(self):
        daf = parse()
        assert daf.full_name == "Rohit Sharma"
        assert daf.education.medium_of_instruction == "English"
        assert daf.cadre_preference == []
        assert daf.attempt_number == 2

    def test_rejects_a_daf_with_no_hobbies_because_boards_always_probe_them(self):
        with pytest.raises(ValidationError):
            parse(hobbies=[])

    @pytest.mark.parametrize(
        "field,value",
        [
            ("home_district", "  "),
            ("optional_subject", ""),
            ("full_name", "   "),
        ],
    )
    def test_requires_the_fields_a_board_cannot_interview_without(self, field, value):
        with pytest.raises(ValidationError):
            parse(**{field: value})

    def test_requires_at_least_one_service_preference(self):
        with pytest.raises(ValidationError):
            parse(service_preference=[])


class TestPortfolios:
    def test_gives_every_board_member_at_least_one_section(self):
        portfolios = to_portfolios(parse())

        assert [p.member_id for p in portfolios] == list(MEMBER_IDS)
        for portfolio in portfolios:
            assert portfolio.sections, (
                f"{portfolio.member_id} ({portfolio.member_name}) owns no DAF section"
            )

    def test_never_gives_the_same_section_to_two_members(self):
        owned = [f for member in BOARD for f in member.owns]
        assert len(set(owned)) == len(owned), f"duplicate ownership in {owned}"

    def test_leaves_no_daf_section_unowned(self):
        owned = {f for member in BOARD for f in member.owns}
        orphaned = [f for f in DAF_FIELDS if f not in owned]
        assert orphaned == [], f"no member questions on: {orphaned}"

    def test_renders_a_portfolio_the_questioning_prompt_can_consume(self):
        academic = next(p for p in to_portfolios(parse()) if p.member_id == "M1")
        prompt = portfolio_to_prompt(academic)

        assert "Sociology" in prompt
        assert "Mechanical Engineering" in prompt
        # The subject expert must not see the candidate's hobbies.
        assert "running" not in prompt


class TestPromptRendering:
    def test_includes_every_section_in_the_full_daf_prompt(self):
        daf = parse()
        prompt = daf_to_prompt(daf)

        for section in to_sections(daf):
            assert section.label in prompt
        assert "Jhansi" in prompt
        assert "IAS" in prompt

    def test_marks_missing_optional_fields_rather_than_emitting_blanks(self):
        assert "(not provided)" in daf_to_prompt(parse())
