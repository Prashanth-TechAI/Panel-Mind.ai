"""Question trees, generated before the interview starts.

This is the single most important latency decision in the system. During a live
turn the member does not invent a question — it walks a pre-built tree and only
rephrases the node in its own voice. That turns a two-second generation into a
two-hundred-millisecond one, which is the whole reason an eight-hundred
millisecond turn budget is achievable.

Generation runs on the cold tier: slow, careful, and off the critical path.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from app.domain.board import BOARD, BOARD_CONDUCT, DafField, MemberId, get_member
from app.domain.daf import Daf, MemberPortfolio, portfolio_to_prompt, to_portfolios
from app.logging_setup import get_logger
from app.providers.llm import ChatMessage, chat_model

# Seed questions per member. Four members × three seeds plus the Chairman gives
# the board far more material than a 28-minute interview can consume, which is
# what lets the Conductor cut a block short without running dry.
SEEDS_PER_MEMBER = 4
FOLLOW_UPS_PER_SEED = 5


class FollowUp(BaseModel):
    """One rung down. Assumes the previous rung was answered adequately."""

    text: str = Field(max_length=220)
    # What this rung is actually measuring. Never spoken aloud; used by the
    # evaluators to know what a good answer at this depth looks like.
    probes: str = Field(max_length=220)


class QuestionNode(BaseModel):
    seed: str = Field(max_length=220)
    # Which DAF section this came from, so nothing is asked out of portfolio.
    section: DafField
    follow_ups: list[FollowUp] = Field(min_length=1, max_length=8)


class MemberQuestionTree(BaseModel):
    member_id: MemberId
    member_name: str
    nodes: list[QuestionNode] = Field(min_length=1, max_length=6)


class _GeneratedTree(BaseModel):
    """What the LLM is asked to return — member identity is added by us."""

    nodes: list[QuestionNode] = Field(min_length=1, max_length=6)


_BRIEF = """{BOARD_CONDUCT}

You are {member.name}, {member.title}. {member.persona}

You are preparing your questions BEFORE the interview. Build a question tree.

Rules for the tree:
- Produce exactly {SEEDS_PER_MEMBER} seed questions, each from a DIFFERENT angle.
- Each seed gets {FOLLOW_UPS_PER_SEED} follow-ups that DESCEND in difficulty.
  Follow-up 1 assumes the seed was answered well. Follow-up 2 assumes 1 was
  answered well, and so on. By the last one you should be at a depth most
  candidates cannot reach — that floor is what you are measuring.
- Every question must come from the candidate's own form. No generic questions.
- You may only question on these sections: {allowed}. Nothing else is yours.
- Set "section" on each node to the section that seed came from.
- "probes" states what the follow-up measures. It is never spoken aloud.
- Spoken register, one question per utterance, no praise.
- SHORT. Most questions are under 15 words. Real board questions sound like:
  "Which division is Ballia in?"  "How many districts are there?"
  "Which language is spoken locally?"  "Can the governor keep it pending?"
  "What was Operation Ajay?"  "Where are their headquarters?"
  Not: "Could you please elaborate on your understanding of..."
- At least half your follow-ups must be RAPID-FIRE FACTUAL checks — one fact,
  one answer, no elaboration invited. Boards use these to find the exact point
  where a candidate stops knowing. Chain them: place, then division, then
  language, then who else speaks it.
- The rest may be judgement questions ("Is this too little too late?") or
  situational ones ("You are the District Magistrate. What do you do first?").
- HARD LIMIT: every "seed" and every follow-up "text" under 200 characters.

Return JSON: {{"nodes": [{{"seed": str, "section": str,
  "follow_ups": [{{"text": str, "probes": str}}]}}]}}"""


def _system_prompt(member, allowed: str) -> str:
    """The questioning brief. Identical whichever way the portfolio was built."""
    return _BRIEF.format(
        BOARD_CONDUCT=BOARD_CONDUCT,
        member=member,
        allowed=allowed,
        SEEDS_PER_MEMBER=SEEDS_PER_MEMBER,
        FOLLOW_UPS_PER_SEED=FOLLOW_UPS_PER_SEED,
    )


def build_prompt(portfolio: MemberPortfolio, daf: Daf) -> list[ChatMessage]:
    """Assemble the generation prompt for one member.

    The member sees only their own portfolio plus the bare identifying facts.
    Withholding the rest of the DAF is what stops five members converging on
    the same three questions.
    """
    member = get_member(portfolio.member_id)
    allowed = ", ".join(member.owns)

    system = _system_prompt(member, allowed)

    user = f"""Candidate: {daf.full_name}, attempt {daf.attempt_number}.

Your portfolio — the only material you may question on:
{portfolio_to_prompt(portfolio)}

Build your question tree."""

    return [ChatMessage("system", system), ChatMessage("user", user)]


async def generate_trees_from_portfolios(
    portfolios: list[MemberPortfolio], candidate: str, attempt: int = 1
) -> tuple[list[MemberQuestionTree], list[str]]:
    """Generate trees from portfolios built any way — typed form or raw upload."""
    log = get_logger(component="questions")
    log.info(f"generating question trees for {len(portfolios)} members", candidate=candidate)

    results = await asyncio.gather(
        *(_tree_for(p, candidate, attempt) for p in portfolios),
        return_exceptions=True,
    )

    trees: list[MemberQuestionTree] = []
    failures: list[str] = []
    for portfolio, result in zip(portfolios, results, strict=True):
        if isinstance(result, BaseException):
            failures.append(f"{portfolio.member_id} ({portfolio.member_name}): {result}")
            log.error(f"{portfolio.member_name} has no questions prepared", error=str(result))
        else:
            trees.append(result)

    return trees, failures


async def _tree_for(
    portfolio: MemberPortfolio, candidate: str, attempt: int
) -> MemberQuestionTree:
    """One member's tree. Members with nothing assigned still get their brief."""
    log = get_logger(component="questions", member_id=portfolio.member_id)
    member = get_member(portfolio.member_id)
    allowed = ", ".join(member.owns)

    material = portfolio_to_prompt(portfolio) or (
        "No form content is yours. Question from your own area of expertise, "
        "anchored to the candidate wherever you can."
    )

    system = _system_prompt(member, allowed)
    user = (
        f"Candidate: {candidate}, attempt {attempt}.\n\n"
        f"Your portfolio — the only material you may question on:\n{material}\n\n"
        "Build your question tree."
    )

    tree, result = await chat_model(
        log, "cold",
        [ChatMessage("system", system), ChatMessage("user", user)],
        _GeneratedTree, temperature=0.8, max_tokens=2400,
    )

    fallback = portfolio.sections[0].field if portfolio.sections else "identity"
    owned = set(member.owns)
    for node in tree.nodes:
        if node.section not in owned:
            node.section = fallback  # type: ignore[assignment]

    log.info(
        f"{portfolio.member_name}: {len(tree.nodes)} seeds, "
        f"{sum(len(n.follow_ups) for n in tree.nodes)} follow-ups",
        seeds=len(tree.nodes),
        tokens=result.completion_tokens,
    )
    return MemberQuestionTree(
        member_id=portfolio.member_id,
        member_name=portfolio.member_name,
        nodes=tree.nodes,
    )


async def generate_tree_for_member(portfolio: MemberPortfolio, daf: Daf) -> MemberQuestionTree:
    """Generate one member's tree. Raises if the model cannot produce valid JSON."""
    log = get_logger(component="questions", member_id=portfolio.member_id)

    tree, result = await chat_model(
        log,
        "cold",
        build_prompt(portfolio, daf),
        _GeneratedTree,
        temperature=0.8,
        max_tokens=2400,
    )

    owned = set(get_member(portfolio.member_id).owns)
    # A model occasionally tags a node with a section it does not own. Rather
    # than discard usable questions, pin them to a section this member holds.
    fallback: DafField = portfolio.sections[0].field if portfolio.sections else next(iter(owned))

    corrected = 0
    for node in tree.nodes:
        if node.section not in owned:
            node.section = fallback
            corrected += 1

    log.info(
        f"{portfolio.member_name}: {len(tree.nodes)} seeds, "
        f"{sum(len(n.follow_ups) for n in tree.nodes)} follow-ups",
        seeds=len(tree.nodes),
        follow_ups=sum(len(n.follow_ups) for n in tree.nodes),
        out_of_portfolio_corrected=corrected,
        tokens=result.completion_tokens,
    )

    return MemberQuestionTree(
        member_id=portfolio.member_id,
        member_name=portfolio.member_name,
        nodes=tree.nodes,
    )


async def generate_all_trees(daf: Daf) -> tuple[list[MemberQuestionTree], list[str]]:
    """Generate every member's tree concurrently.

    Returns the trees that succeeded plus a list of failures. One member
    failing does not block the interview — the Conductor simply skips a board
    member who has nothing prepared, which is far better than refusing to start.
    """
    log = get_logger(component="questions")
    portfolios = to_portfolios(daf)

    log.info(f"generating question trees for {len(portfolios)} members", candidate=daf.full_name)

    results = await asyncio.gather(
        *(generate_tree_for_member(p, daf) for p in portfolios),
        return_exceptions=True,
    )

    trees: list[MemberQuestionTree] = []
    failures: list[str] = []

    for portfolio, result in zip(portfolios, results, strict=True):
        if isinstance(result, BaseException):
            member_name = portfolio.member_name
            failures.append(f"{portfolio.member_id} ({member_name}): {result}")
            log.error(
                f"{member_name} has no questions prepared",
                member_id=portfolio.member_id,
                error=str(result),
            )
        else:
            trees.append(result)

    if failures:
        log.warning(
            f"{len(failures)} of {len(BOARD)} members failed to prepare",
            failures=failures,
        )

    return trees, failures
