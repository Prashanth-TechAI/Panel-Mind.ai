"""The Detailed Application Form.

UPSC boards question almost entirely from the DAF — home district, optional
subject, hobbies, service preference. Without it the interview is a generic
quiz. This schema mirrors the real form closely enough that a candidate can
transcribe theirs field for field.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from app.domain.board import BOARD, DafField, MemberId

EMPTY = "(not provided)"


def _stripped(value: str) -> str:
    return value.strip()


class Qualification(BaseModel):
    """One row of the real DAF's education table.

    Boards read this table across, not down: a first in 12th and a third in
    graduation is a question, and it cannot be asked if the rows are flattened.
    """

    board_or_university: str = ""
    subjects: str = ""
    year_of_passing: str = ""
    division_or_grade: str = ""
    percentage: str = ""


class Education(BaseModel):
    graduation_subject: str = Field(min_length=1)
    graduation_college: str = Field(min_length=1)
    university: str = ""
    post_graduation: str = ""
    medium_of_instruction: str = "English"
    # The full table, as printed on DAF-I field 14.2.
    tenth: Qualification = Field(default_factory=Qualification)
    twelfth: Qualification = Field(default_factory=Qualification)
    graduation: Qualification = Field(default_factory=Qualification)

    @field_validator("graduation_subject", "graduation_college", mode="after")
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned


class Daf(BaseModel):
    # --- Identity ---
    full_name: str = Field(min_length=1)
    roll_number: str = ""
    date_of_birth: str = ""
    gender: str = ""
    marital_status: str = ""
    category: str = ""  # General / OBC / SC / ST / EWS
    # The Chairman's richest thread in a real board comes from here.
    fathers_occupation: str = ""
    mothers_occupation: str = ""

    # --- Home ---
    # Permanent, not correspondence: the board asks about your home district.
    home_state: str = Field(min_length=1)
    home_district: str = Field(min_length=1)
    home_town: str = ""
    mother_tongue: str = ""

    # --- Academic ---
    education: Education
    optional_subject: str = Field(min_length=1)

    # --- Personality ---
    hobbies: list[str] = Field(min_length=1, max_length=5)
    sports_and_achievements: list[str] = Field(default_factory=list, max_length=5)
    positions_of_responsibility: list[str] = Field(default_factory=list, max_length=5)

    # --- Career ---
    work_experience: list[str] = Field(default_factory=list, max_length=5)
    current_employment: str = ""
    service_preference: list[str] = Field(min_length=1, max_length=6)
    cadre_preference: list[str] = Field(default_factory=list, max_length=6)

    # --- Personality (DAF-II) ---
    prizes_and_medals: list[str] = Field(default_factory=list, max_length=5)
    extracurricular: list[str] = Field(default_factory=list, max_length=5)

    # --- Context ---
    languages_known: list[str] = Field(default_factory=list, max_length=6)
    attempt_number: int = Field(default=1, ge=1, le=9)
    # "This is your fourth attempt — what changed?" is a standard question.
    previous_attempts: str = ""
    exam_centre: str = ""

    @field_validator("full_name", "home_state", "home_district", "optional_subject", mode="after")
    @classmethod
    def _required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("is required")
        return cleaned

    @field_validator(
        "hobbies",
        "sports_and_achievements",
        "positions_of_responsibility",
        "work_experience",
        "service_preference",
        "cadre_preference",
        "languages_known",
        "prizes_and_medals",
        "extracurricular",
        mode="after",
    )
    @classmethod
    def _clean_list(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v.strip()]

    @field_validator("hobbies", mode="after")
    @classmethod
    def _hobbies_required(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("List at least one hobby — boards always probe these")
        return values

    @field_validator("service_preference", mode="after")
    @classmethod
    def _service_required(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("Give at least your first service preference")
        return values


@dataclass(frozen=True, slots=True)
class DafSection:
    field: DafField
    label: str
    # Rendered as plain prose for the question-generation prompt.
    content: str


def _listed(items: list[str]) -> str:
    return "; ".join(items) if items else EMPTY


def _row(q) -> str:
    """One education row as prose, or "(not provided)" when blank."""
    parts = [
        q.board_or_university, q.subjects, q.year_of_passing,
        q.division_or_grade, q.percentage,
    ]
    filled = [p for p in parts if p]
    return ", ".join(filled) if filled else EMPTY


def to_sections(daf: Daf) -> list[DafSection]:
    """Flatten a DAF into labelled sections keyed by the field each member owns."""
    edu = daf.education
    university = f", {edu.university}" if edu.university else ""

    return [
        DafSection(
            field="identity",
            label="Identity",
            content=(
                f"{daf.full_name}, attempt {daf.attempt_number}. "
                f"{daf.gender or ''} {daf.marital_status or ''}. "
                f"Category: {daf.category or EMPTY}. "
                f"Previous attempts: {daf.previous_attempts or EMPTY}."
            ),
        ),
        DafSection(
            field="family_background",
            label="Family background",
            content=(
                f"Father's occupation: {daf.fathers_occupation or EMPTY}. "
                f"Mother's occupation: {daf.mothers_occupation or EMPTY}. "
                "Probe what those occupations taught them, and the problems of "
                "that profession as the candidate would know them first-hand."
            ),
        ),
        DafSection(
            field="languages",
            label="Languages and dialects",
            content=(
                f"Mother tongue: {daf.mother_tongue or EMPTY}. "
                f"Also speaks: {_listed(daf.languages_known)}. "
                f"Home town {daf.home_town or daf.home_district}, {daf.home_state} — "
                "ask which dialect is spoken locally, and where that language is "
                "spoken outside India."
            ),
        ),
        DafSection(
            field="home_state",
            label="Home state and district",
            content=(
                f"{daf.home_town + ', ' if daf.home_town else ''}"
                f"{daf.home_district}, {daf.home_state}."
            ),
        ),
        DafSection(
            field="education",
            label="Education",
            content=(
                f"Graduation in {edu.graduation_subject} from "
                f"{edu.graduation_college}{university}. "
                f"Post-graduation: {edu.post_graduation or EMPTY}. "
                f"Medium of instruction: {edu.medium_of_instruction}. "
                f"10th: {_row(edu.tenth)}. 12th: {_row(edu.twelfth)}. "
                f"Graduation: {_row(edu.graduation)}."
            ),
        ),
        DafSection(
            field="optional_subject",
            label="Optional subject",
            content=daf.optional_subject,
        ),
        DafSection(field="hobbies", label="Hobbies", content=_listed(daf.hobbies)),
        DafSection(
            field="sports",
            label="Sports and achievements",
            content=(
                f"{_listed(daf.sports_and_achievements)}. "
                f"Prizes and medals: {_listed(daf.prizes_and_medals)}. "
                f"Extra-curricular: {_listed(daf.extracurricular)}."
            ),
        ),
        DafSection(
            field="positions_of_responsibility",
            label="Positions of responsibility",
            content=_listed(daf.positions_of_responsibility),
        ),
        DafSection(
            field="work_experience",
            label="Work experience",
            content=(
                f"{_listed(daf.work_experience)}. "
                f"Currently: {daf.current_employment or EMPTY}."
            ),
        ),
        DafSection(
            field="service_preference",
            label="Service and cadre preference",
            content=(
                f"Services: {_listed(daf.service_preference)}. "
                f"Cadre: {_listed(daf.cadre_preference)}."
            ),
        ),
        DafSection(
            field="current_affairs",
            label="Current affairs",
            content=(
                "No DAF content. Question from national and international affairs, "
                "government schemes and economic policy, anchored where possible to "
                f"the candidate's home state ({daf.home_state}) and subject "
                f"({edu.graduation_subject})."
            ),
        ),
    ]


@dataclass(frozen=True, slots=True)
class MemberPortfolio:
    member_id: MemberId
    member_name: str
    sections: tuple[DafSection, ...]


def to_portfolios(daf: Daf) -> list[MemberPortfolio]:
    """Split the DAF across the board.

    Each member sees only the sections they own, which is what stops five agents
    asking five variations of "tell me about your hobbies".
    """
    by_field = {s.field: s for s in to_sections(daf)}

    return [
        MemberPortfolio(
            member_id=member.id,
            member_name=member.name,
            sections=tuple(by_field[f] for f in member.owns if f in by_field),
        )
        for member in BOARD
    ]


def portfolio_to_prompt(portfolio: MemberPortfolio) -> str:
    """Compact prose form of a portfolio, for injecting into a prompt."""
    return "\n".join(f"{s.label}: {s.content}" for s in portfolio.sections)


def daf_to_prompt(daf: Daf) -> str:
    """Every field of the DAF as prose.

    The Chairman's opening and the evaluators both need the whole picture rather
    than one member's slice.
    """
    return "\n".join(f"{s.label}: {s.content}" for s in to_sections(daf))
