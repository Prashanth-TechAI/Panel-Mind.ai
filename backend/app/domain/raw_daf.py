"""Using an uploaded DAF as-is, without squeezing it into our own schema.

A real DAF carries around 195 fields. Mapping those onto the ~30 our form
models threw away everything else — the board never saw the education table's
individual rows, the exam history, the certificate details that hint at a
candidate's background.

So a PDF is no longer mapped. Its fields are handed to the five members
directly, and one cold-tier call decides which member should own each. That
means a form label nobody anticipated — "14.2 Educational Qualifications —
B.TECH — Division/Grade" — reaches the subject expert without anyone having to
enumerate it in advance.

The typed form still produces a Daf. Both paths end up as labelled prose, which
is all question generation ever consumed.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.board import BOARD, MEMBER_IDS, MemberId, get_member
from app.domain.daf import DafSection, MemberPortfolio
from app.logging_setup import get_logger
from app.providers.llm import ChatMessage, chat_model

# Labels that are pure administration — certificate numbers, issue dates, photo
# IDs. A board never asks about them and they crowd out the useful material.
_NOISE = (
    "certificate no", "date of issue", "photo-id", "photo id", "rid",
    "signature", "declaration", "fee", "payment", "captcha", "verification",
    "upload", "fax no", "pin code", "pincode",
)


def is_useful(label: str) -> bool:
    low = label.lower()
    return not any(n in low for n in _NOISE)


class _Assignment(BaseModel):
    """Which member owns which of the form's own labels."""

    M0: list[str] = Field(default_factory=list)
    M1: list[str] = Field(default_factory=list)
    M2: list[str] = Field(default_factory=list)
    M3: list[str] = Field(default_factory=list)
    M4: list[str] = Field(default_factory=list)


def _brief() -> str:
    return "\n".join(f"{m.id} — {m.name}, {m.title}: {m.role}" for m in BOARD)


_PROMPT = """You are dividing a candidate's UPSC application form across an
interview board, so that no two members question on the same material.

The board:
{brief}

Rules:
- Assign every label to exactly ONE member. Never repeat a label.
- Anything about the candidate themselves, their family, their service
  preference or employment goes to M0.
- Education, degrees, marks, subjects go to M1.
- Home state, district, town, and positions of responsibility go to M2.
- M3 owns nothing from the form — they question on current affairs — so leave
  M3 empty.
- Hobbies, sports, prizes, languages and anything personal go to M4.
- Omit a label entirely if no member would ever ask about it.

Return JSON: {{"M0": [labels], "M1": [...], "M2": [...], "M3": [], "M4": [...]}}"""


async def portfolios_from_raw(raw_fields: dict[str, str]) -> list[MemberPortfolio]:
    """Split an uploaded form's own fields across the board.

    Falls back to a keyword split if the model cannot decide — a convened board
    with a rough division beats no interview at all.
    """
    log = get_logger(component="raw_daf")
    usable = {k: v for k, v in raw_fields.items() if is_useful(k) and str(v).strip()}

    log.info(
        f"dividing {len(usable)} usable field(s) across the board",
        total=len(raw_fields),
        usable=len(usable),
    )

    try:
        assignment, _ = await chat_model(
            log,
            "cold",
            [
                ChatMessage("system", _PROMPT.format(brief=_brief())),
                ChatMessage("user", "\n".join(f"- {k}" for k in usable)),
            ],
            _Assignment,
            temperature=0.1,
            max_tokens=4000,
        )
        owned = assignment.model_dump()
    except Exception as exc:
        log.warning("assignment failed — falling back to a keyword split", error=str(exc))
        owned = _keyword_split(usable)

    portfolios: list[MemberPortfolio] = []
    for member_id in MEMBER_IDS:
        labels = [lbl for lbl in owned.get(member_id, []) if lbl in usable]
        sections = tuple(
            DafSection(field="identity", label=lbl, content=str(usable[lbl]))  # type: ignore[arg-type]
            for lbl in labels
        )
        portfolios.append(
            MemberPortfolio(
                member_id=member_id,
                member_name=get_member(member_id).name,
                sections=sections,
            )
        )

    log.info(
        "form divided",
        split={p.member_id: len(p.sections) for p in portfolios},
    )
    return portfolios


_KEYWORDS: dict[MemberId, tuple[str, ...]] = {
    "M1": ("education", "qualification", "degree", "subject", "school", "board",
           "university", "college", "medium", "optional", "graduat", "score", "division"),
    "M2": ("district", "state", "city", "town", "address", "domicile",
           "position", "responsib"),
    "M4": ("hobb", "sport", "prize", "medal", "language", "mother tongue",
           "extra", "interest", "ncc", "nss"),
    "M0": ("name", "father", "mother", "service", "cadre", "employ", "attempt",
           "gender", "marital", "community", "category", "date of birth"),
}


def _keyword_split(usable: dict[str, str]) -> dict[str, list[str]]:
    """Deterministic fallback, so an LLM outage never blocks an interview."""
    out: dict[str, list[str]] = {m: [] for m in MEMBER_IDS}
    for label in usable:
        low = label.lower()
        for member_id, needles in _KEYWORDS.items():
            if any(n in low for n in needles):
                out[member_id].append(label)
                break
        else:
            out["M0"].append(label)
    return out


def candidate_name(raw_fields: dict[str, str]) -> str:
    """The candidate's name, however this particular form spelled the label."""
    for key in ("Name", "name", "Candidate Name", "1. Name", "Full Name"):
        value = str(raw_fields.get(key, "")).strip()
        if value:
            return value
    for key, value in raw_fields.items():
        if key.strip().lower().endswith("name") and str(value).strip():
            return str(value).strip()
    return "Candidate"
