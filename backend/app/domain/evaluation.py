"""The evaluation plane.

Five evaluators score the same transcript through five different lenses, each
weighted toward the traits its member cares about, and none of them ever sees
another's verdict. That independence is the point: a consolidated mark built
from five genuinely separate readings is worth more than one model's opinion
rendered five times.

This runs entirely off the critical path. It may take a minute; nobody is
waiting on it, so it uses the slow, careful tier.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.board import (
    BOARD,
    TRAIT_LABELS,
    UPSC_TRAITS,
    MemberId,
    UpscTrait,
    get_member,
)
from app.domain.daf import Daf, daf_to_prompt
from app.logging_setup import get_logger
from app.providers.llm import ChatMessage, chat_model

# The UPSC personality test is marked out of 275. Reported marks cluster
# between roughly 150 and 210; anything outside that is exceptional either way.
MAX_MARKS = 275
FLOOR_MARKS = 90


# Evaluators consistently wrote substantive trait notes past a 300-char cap and
# burned a corrective retry every time. The limit is now generous enough for a
# real remark, and — more importantly — it is stated in the prompt below.
TRAIT_NOTE_LIMIT = 450


class TraitScore(BaseModel):
    trait: UpscTrait
    score: int = Field(ge=0, le=10)
    note: str = Field(max_length=TRAIT_NOTE_LIMIT)


FlagKind = Literal[
    "bluff",
    "evasive",
    "rambling",
    "admitted_ignorance",
    "one_sided",
    "strong",
]


class AnswerFlag(BaseModel):
    """A specific moment worth replaying to the candidate."""

    kind: FlagKind
    quote: str = Field(max_length=300)
    comment: str = Field(max_length=400)


class MemberScorecard(BaseModel):
    member_id: MemberId
    member_name: str
    traits: list[TraitScore] = Field(min_length=1)
    marks: int = Field(ge=0, le=MAX_MARKS)
    remark: str = Field(max_length=600)
    flags: list[AnswerFlag] = Field(default_factory=list, max_length=8)


class _EvaluatorOutput(BaseModel):
    """What one evaluator returns. Identity is added by us, not the model."""

    traits: list[TraitScore] = Field(min_length=1)
    marks: int = Field(ge=0, le=MAX_MARKS)
    remark: str = Field(max_length=600)
    flags: list[AnswerFlag] = Field(default_factory=list, max_length=8)


class Improvement(BaseModel):
    area: str = Field(max_length=120)
    why: str = Field(max_length=400)
    action: str = Field(max_length=400)


class Consolidation(BaseModel):
    summary: str = Field(max_length=900)
    lost_marks: list[str] = Field(default_factory=list, max_length=6)
    improvements: list[Improvement] = Field(default_factory=list, max_length=6)


@dataclass(slots=True)
class Utterance:
    speaker: str
    member_id: str | None
    text: str
    at_ms: int


# --- Objective signals: measured, not judged ---------------------------------

FILLERS = (
    "um",
    "uh",
    "basically",
    "actually",
    "you know",
    "i mean",
    "sort of",
    "kind of",
    "like",
)

_DONT_KNOW = re.compile(
    r"\b(i (do not|don't) know|i am not (sure|aware)|i'm not (sure|aware)|no idea)\b",
    re.IGNORECASE,
)


class ObjectiveSignals(BaseModel):
    """Facts about how the candidate spoke. No model involved, so no opinion."""

    answers: int
    total_words: int
    average_words_per_answer: float
    longest_answer_words: int
    filler_ratio: float
    admitted_ignorance_count: int
    interruptions_taken: int


def extract_signals(transcript: list[Utterance], ramble_threshold: int = 190) -> ObjectiveSignals:
    answers = [u for u in transcript if u.member_id is None]
    words = [len(u.text.split()) for u in answers]
    total = sum(words)

    filler_hits = 0
    for answer in answers:
        lowered = f" {answer.text.lower()} "
        for filler in FILLERS:
            filler_hits += lowered.count(f" {filler} ")

    return ObjectiveSignals(
        answers=len(answers),
        total_words=total,
        average_words_per_answer=round(total / len(answers), 1) if answers else 0.0,
        longest_answer_words=max(words, default=0),
        filler_ratio=round(filler_hits / total, 4) if total else 0.0,
        admitted_ignorance_count=sum(1 for a in answers if _DONT_KNOW.search(a.text)),
        # A board only interrupts when the candidate has overrun.
        interruptions_taken=sum(1 for w in words if w > ramble_threshold),
    )


def render_transcript(transcript: list[Utterance]) -> str:
    lines = []
    for utterance in transcript:
        who = "CANDIDATE" if utterance.member_id is None else utterance.speaker.upper()
        lines.append(f"[{utterance.at_ms // 1000}s] {who}: {utterance.text}")
    return "\n".join(lines) or "(no exchanges recorded)"


# --- The five evaluators -----------------------------------------------------

_RUBRIC = "\n".join(f"- {key}: {label}" for key, label in TRAIT_LABELS.items())


def build_evaluator_prompt(
    member_id: MemberId, daf: Daf, transcript: list[Utterance], signals: ObjectiveSignals
) -> list[ChatMessage]:
    member = get_member(member_id)
    weighted = ", ".join(TRAIT_LABELS[t] for t in member.weighs)

    system = f"""You are {member.name}, {member.title}, scoring a UPSC Civil Services
personality test you have just sat on. {member.persona}

Score the candidate on all seven official UPSC traits, 0-10 each:
{_RUBRIC}

You weigh these most heavily: {weighted}. Score the others honestly regardless.

Then award marks out of {MAX_MARKS}. Calibration, from real reported marks:
- below 150: weak, would not clear
- 150-175: average
- 175-200: good
- 200-220: very strong
- above 220: exceptional and rare
A blank or near-silent interview scores near {FLOOR_MARKS}. Do not be generous;
boards are not. Most candidates land between 160 and 190.

Flag specific moments. Be ruthless about these two above all:
- "bluff": they asserted something they did not know. Quote it.
- "admitted_ignorance": they said "I don't know". This is a POSITIVE signal
  of integrity — reward it, never penalise it.
Also flag "evasive", "rambling", "one_sided", and "strong" where they apply.
Every flag must quote the candidate's own words.

HARD LENGTH LIMITS — exceeding any of these makes the response invalid:
- each trait "note": under {TRAIT_NOTE_LIMIT} characters
- "remark": under 600 characters
- each flag "quote": under 300 characters; each flag "comment": under 400

Return JSON:
{{"traits": [{{"trait": str, "score": int, "note": str}}],
  "marks": int, "remark": str,
  "flags": [{{"kind": str, "quote": str, "comment": str}}]}}"""

    user = f"""Candidate's form:
{daf_to_prompt(daf)}

Measured facts about their speech (do not re-derive these, use them):
- answers given: {signals.answers}
- average answer length: {signals.average_words_per_answer} words
- longest answer: {signals.longest_answer_words} words
- filler word ratio: {signals.filler_ratio:.2%}
- times they said "I don't know": {signals.admitted_ignorance_count}
- times the board had to interrupt them: {signals.interruptions_taken}

Full record of proceedings:
{render_transcript(transcript)}

Score them."""

    return [ChatMessage("system", system), ChatMessage("user", user)]


async def evaluate_by_member(
    member_id: MemberId, daf: Daf, transcript: list[Utterance], signals: ObjectiveSignals
) -> MemberScorecard:
    member = get_member(member_id)
    log = get_logger(component="evaluation", member_id=member_id)

    output, _ = await chat_model(
        log,
        "cold",
        build_evaluator_prompt(member_id, daf, transcript, signals),
        _EvaluatorOutput,
        temperature=0.3,
        max_tokens=2000,
    )

    log.info(
        f"{member.name} scored {output.marks}/{MAX_MARKS}",
        marks=output.marks,
        flags=[f.kind for f in output.flags],
    )

    return MemberScorecard(
        member_id=member_id,
        member_name=member.name,
        traits=output.traits,
        marks=output.marks,
        remark=output.remark,
        flags=output.flags,
    )


class BoardReport(BaseModel):
    candidate: str
    consolidated_marks: int
    scorecards: list[MemberScorecard]
    trait_averages: dict[str, float]
    signals: ObjectiveSignals
    summary: str
    lost_marks: list[str]
    improvements: list[Improvement]
    evaluators_failed: list[str] = Field(default_factory=list)
    # An AI mark is not a UPSC mark. This travels with the score, always.
    calibration_note: str = (
        "Indicative only. This score is produced by an AI board and is not "
        "calibrated against actual UPSC marks. Use it to compare your own "
        "attempts over time, not to predict your result."
    )


def average_traits(scorecards: list[MemberScorecard]) -> dict[str, float]:
    """Mean score per trait across every evaluator that returned one."""
    totals: dict[str, list[int]] = {trait: [] for trait in UPSC_TRAITS}
    for card in scorecards:
        for trait in card.traits:
            totals[trait.trait].append(trait.score)

    return {
        trait: round(sum(scores) / len(scores), 1) if scores else 0.0
        for trait, scores in totals.items()
    }


async def consolidate(
    daf: Daf,
    scorecards: list[MemberScorecard],
    signals: ObjectiveSignals,
    transcript: list[Utterance],
) -> Consolidation:
    log = get_logger(component="evaluation.consolidate")

    cards = "\n\n".join(
        f"{c.member_name} — {c.marks}/{MAX_MARKS}\n"
        f"  remark: {c.remark}\n"
        + "\n".join(f"  {t.trait}: {t.score}/10 — {t.note}" for t in c.traits)
        + ("\n  flags: " + "; ".join(f"[{f.kind}] {f.quote}" for f in c.flags) if c.flags else "")
        for c in scorecards
    )

    system = """You are the Secretary to a UPSC interview board, writing the
candidate's feedback after the board has scored them independently.

Write for the candidate. Be direct and specific — quote their own words. Never
console them and never flatter them. Where the board disagreed, say so; that
disagreement is information.

"lost_marks": the specific moments that cost them, each naming what happened.
"improvements": concrete, practisable changes. Not "be more confident" — say
what to do differently and why it cost them marks here.

Return JSON: {"summary": str, "lost_marks": [str],
  "improvements": [{"area": str, "why": str, "action": str}]}"""

    user = f"""Candidate: {daf.full_name}, attempt {daf.attempt_number}.

Independent scorecards from the five members:
{cards}

Measured speech: {signals.answers} answers, {signals.average_words_per_answer} words
average, longest {signals.longest_answer_words}, filler ratio
{signals.filler_ratio:.2%}, admitted ignorance {signals.admitted_ignorance_count}x,
interrupted {signals.interruptions_taken}x.

Record of proceedings:
{render_transcript(transcript)}

Write their feedback."""

    result, _ = await chat_model(
        log,
        "cold",
        [ChatMessage("system", system), ChatMessage("user", user)],
        Consolidation,
        temperature=0.4,
        max_tokens=2000,
    )
    return result


async def evaluate_interview(
    daf: Daf, transcript: list[Utterance], banked: list[dict] | None = None
) -> BoardReport:
    """Score a finished interview.

    Every evaluator runs concurrently and independently. One failing costs that
    member's scorecard, not the whole report — a candidate who sat a full
    interview must always get feedback.
    """
    log = get_logger(component="evaluation")
    signals = extract_signals(transcript)

    # Judgements made in the room, while each answer was fresh.
    if banked:
        rendered = "\n".join(
            f"Turn {b['turn']} [{b['verdict']}] Q: {b['question']} | A: {b['answer']}"
            f"{' — ' + b['note'] if b.get('note') else ''}"
            for b in banked
        )
        transcript = [
            *transcript,
            Utterance(
                speaker="RECORD",
                member_id=None,
                text=f"Verdicts recorded during the interview:\n{rendered}",
                at_ms=0,
            ),
        ]

    log.info(
        "evaluating interview",
        candidate=daf.full_name,
        exchanges=len(transcript),
        answers=signals.answers,
    )

    results = await asyncio.gather(
        *(evaluate_by_member(m.id, daf, transcript, signals) for m in BOARD),
        return_exceptions=True,
    )

    scorecards: list[MemberScorecard] = []
    failed: list[str] = []

    for member, result in zip(BOARD, results, strict=True):
        if isinstance(result, BaseException):
            failed.append(f"{member.id} ({member.name}): {result}")
            log.error(f"{member.name} could not score", error=str(result))
        else:
            scorecards.append(result)

    if not scorecards:
        raise RuntimeError(f"No evaluator produced a scorecard: {failed}")

    consolidated_marks = round(sum(c.marks for c in scorecards) / len(scorecards))

    try:
        written = await consolidate(daf, scorecards, signals, transcript)
    except Exception as exc:
        # The marks survive even if the prose does not.
        log.error("consolidation failed — returning scores without written feedback", error=str(exc))
        written = Consolidation(
            summary="Written feedback could not be generated. Your marks and the "
            "individual members' remarks below are unaffected.",
            lost_marks=[],
            improvements=[],
        )

    log.info(
        f"consolidated {consolidated_marks}/{MAX_MARKS} from {len(scorecards)} evaluators",
        marks=consolidated_marks,
        evaluators=len(scorecards),
        failed=len(failed),
    )

    return BoardReport(
        candidate=daf.full_name,
        consolidated_marks=consolidated_marks,
        scorecards=scorecards,
        trait_averages=average_traits(scorecards),
        signals=signals,
        summary=written.summary,
        lost_marks=written.lost_marks,
        improvements=written.improvements,
        evaluators_failed=failed,
    )
