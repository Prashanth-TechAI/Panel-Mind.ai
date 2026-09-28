"""What an aspirant has actually earned.

Every award here is derived from something recorded: an interview that was
sat, a mark that was awarded, a verdict banked while the answer was fresh.
Nothing is granted for signing up, and nothing is granted on a schedule — if
the database cannot show the evidence, the award is not held.

That constraint is the point. An award the product hands out for turning up is
worth nothing to someone preparing for a board that hands out nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class Award:
    key: str
    title: str
    detail: str
    held: bool
    # What still has to happen, when it is not held yet.
    progress: str = ""


def awards_from(facts: dict) -> list[Award]:
    """Turn measured facts into the list of awards, held and unheld alike."""
    mocks: int = facts.get("mocks", 0)
    completed: int = facts.get("completed", 0)
    best = facts.get("best_marks")
    verdicts: dict = facts.get("verdicts", {})
    candour = verdicts.get("admitted_ignorance", 0)
    bluffs = verdicts.get("bluffed", 0)
    judged = sum(verdicts.values())

    def marks_progress(target: int) -> str:
        if best is None:
            return "Sit a board and be scored"
        return f"Best so far {best}/275 — {target} needed"

    return [
        Award(
            key="first_board",
            title="First board",
            detail="Faced all five members once.",
            held=mocks >= 1,
            progress="" if mocks >= 1 else "Sit your first mock",
        ),
        Award(
            key="five_boards",
            title="Five boards",
            detail="Five interviews on the record.",
            held=mocks >= 5,
            progress="" if mocks >= 5 else f"{mocks} of 5 sat",
        ),
        Award(
            key="ten_boards",
            title="Ten boards",
            detail="Ten interviews on the record.",
            held=mocks >= 10,
            progress="" if mocks >= 10 else f"{mocks} of 10 sat",
        ),
        Award(
            key="went_the_distance",
            title="Went the distance",
            detail="Sat a board through to the Chairman's closing.",
            held=completed >= 1,
            progress="" if completed >= 1 else "Reach the end of an interview",
        ),
        Award(
            key="candour",
            title="Candour",
            detail='Said "I don\'t know" rather than bluffing. Boards reward this.',
            held=candour >= 1,
            progress="" if candour >= 1 else "Admit a gap instead of covering it",
        ),
        Award(
            key="no_bluff",
            title="Nothing invented",
            detail="Twenty judged answers without a single bluff.",
            held=judged >= 20 and bluffs == 0,
            progress=(
                ""
                if judged >= 20 and bluffs == 0
                else f"{judged} answers judged, {bluffs} bluffed"
            ),
        ),
        Award(
            key="above_the_line",
            title="Above the line",
            detail="Scored 175 or more — the range that clears.",
            held=bool(best and best >= 175),
            progress="" if best and best >= 175 else marks_progress(175),
        ),
        Award(
            key="distinction",
            title="Distinction",
            detail="Scored 200 or more. Rare in the real thing.",
            held=bool(best and best >= 200),
            progress="" if best and best >= 200 else marks_progress(200),
        ),
    ]


def summarise(facts: dict) -> dict:
    """The profile page's whole awards section, in one payload."""
    awards = awards_from(facts)
    return {
        "held": sum(1 for a in awards if a.held),
        "total": len(awards),
        "awards": [asdict(a) for a in awards],
        "stats": {
            "mocks": facts.get("mocks", 0),
            "completed": facts.get("completed", 0),
            "best_marks": facts.get("best_marks"),
            "average_marks": facts.get("average_marks"),
            "answers_given": facts.get("answers_given", 0),
            "first_at": facts.get("first_at"),
            "last_at": facts.get("last_at"),
        },
    }
