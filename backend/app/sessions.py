"""Interview session store.

Holds the prepared material for a session between the moment the candidate
submits their DAF and the moment the voice worker joins the room.

This implementation is in-process and therefore single-replica. The interface
is deliberately narrow — ``create``, ``get``, ``finish`` — so swapping in Redis
or Postgres when you scale past one API pod is a contained change and nothing
above this module has to move.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from livekit import api

from app.config import get_settings
from app.domain.daf import Daf
from app.domain.questions import MemberQuestionTree
from app.logging_setup import get_logger, new_id

# Sessions older than this are dropped. An interview is ~28 minutes; this gives
# generous room for a candidate who prepares and then walks away.
SESSION_TTL_S = 2 * 60 * 60


@dataclass(slots=True)
class Utterance:
    speaker: str
    member_id: str | None
    text: str
    at_ms: int


@dataclass(slots=True)
class InterviewSession:
    id: str
    room_name: str
    daf: Daf
    trees: list[MemberQuestionTree]
    preparation_failures: list[str]
    # Who sat this interview. None for anonymous/legacy sessions.
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    transcript: list[Utterance] = field(default_factory=list)
    ended_reason: str | None = None
    # Cached consolidated mark, so the dashboard need not re-evaluate.
    marks: int | None = None

    @property
    def prepared_members(self) -> list[str]:
        return [t.member_id for t in self.trees]


# Where prepared interviews are kept between restarts.
STORE_PATH = Path(os.environ.get("BOARD_SESSION_STORE", ".sessions.json"))


class SessionStore:
    """Prepared interviews, persisted to disk.

    Holding these in memory alone meant every API restart silently orphaned
    every convened room: the worker could no longer resolve the session, so it
    refused the job and the candidate sat in an empty room. Preparing an
    interview costs five LLM calls and half a minute — it must outlive a
    process.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._sessions: dict[str, InterviewSession] = {}
        self._by_room: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._log = get_logger(component="sessions")
        self._path = path or STORE_PATH
        self._load()

    # --- persistence -----------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
        except Exception as exc:
            self._log.warning("could not read the session store", error=str(exc))
            return

        cutoff = time.time() - SESSION_TTL_S
        for row in raw.get("sessions", []):
            if row.get("created_at", 0) < cutoff:
                continue
            try:
                session = InterviewSession(
                    id=row["id"],
                    room_name=row["room_name"],
                    daf=Daf.model_validate(row["daf"]),
                    trees=[MemberQuestionTree.model_validate(t) for t in row["trees"]],
                    preparation_failures=row.get("preparation_failures", []),
                    user_id=row.get("user_id"),
                    created_at=row["created_at"],
                    transcript=[Utterance(**u) for u in row.get("transcript", [])],
                    ended_reason=row.get("ended_reason"),
                    marks=row.get("marks"),
                )
            except Exception as exc:
                self._log.warning("skipping an unreadable session", error=str(exc))
                continue
            self._sessions[session.id] = session
            self._by_room[session.room_name] = session.id

        if self._sessions:
            self._log.info(f"restored {len(self._sessions)} prepared interview(s)")

    def _persist(self) -> None:
        """Write through on every change. Called with the lock held."""
        try:
            payload = {
                "sessions": [
                    {
                        "id": s.id,
                        "room_name": s.room_name,
                        "daf": s.daf.model_dump(),
                        "trees": [t.model_dump() for t in s.trees],
                        "preparation_failures": s.preparation_failures,
                        "user_id": s.user_id,
                        "created_at": s.created_at,
                        "transcript": [
                            {
                                "speaker": u.speaker,
                                "member_id": u.member_id,
                                "text": u.text,
                                "at_ms": u.at_ms,
                            }
                            for u in s.transcript
                        ],
                        "ended_reason": s.ended_reason,
                        "marks": s.marks,
                    }
                    for s in self._sessions.values()
                ]
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload))
            tmp.replace(self._path)  # atomic: a crash mid-write cannot corrupt it
        except Exception as exc:
            self._log.warning("could not persist sessions", error=str(exc))

    async def create(
        self,
        daf: Daf,
        trees: list[MemberQuestionTree],
        failures: list[str],
        user_id: str | None = None,
    ) -> InterviewSession:
        session_id = new_id("ses")
        session = InterviewSession(
            id=session_id,
            room_name=f"board-{session_id}",
            daf=daf,
            trees=trees,
            preparation_failures=failures,
            user_id=user_id,
        )

        async with self._lock:
            self._evict_expired()
            self._sessions[session.id] = session
            self._by_room[session.room_name] = session.id
            self._persist()

        self._log.info(
            "interview session created",
            session_id=session.id,
            room=session.room_name,
            candidate=daf.full_name,
            prepared_members=session.prepared_members,
        )
        return session

    async def get(self, session_id: str) -> InterviewSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def get_by_room(self, room_name: str) -> InterviewSession | None:
        async with self._lock:
            session_id = self._by_room.get(room_name)
            return self._sessions.get(session_id) if session_id else None

    async def append_utterance(self, session_id: str, utterance: Utterance) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.transcript.append(utterance)
                self._persist()

    async def for_user(self, user_id: str) -> list[InterviewSession]:
        """Every interview this aspirant has sat, newest first."""
        async with self._lock:
            return sorted(
                (s for s in self._sessions.values() if s.user_id == user_id),
                key=lambda s: s.created_at,
                reverse=True,
            )

    async def record_marks(self, session_id: str, marks: int) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.marks = marks
                self._persist()

    async def finish(self, session_id: str, reason: str) -> InterviewSession | None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.ended_reason = reason
                self._persist()
        return session

    def _evict_expired(self) -> None:
        cutoff = time.time() - SESSION_TTL_S
        stale = [s.id for s in self._sessions.values() if s.created_at < cutoff]
        for session_id in stale:
            session = self._sessions.pop(session_id, None)
            if session is not None:
                self._by_room.pop(session.room_name, None)
        if stale:
            self._log.info(f"evicted {len(stale)} expired session(s)", count=len(stale))


store = SessionStore()


def mint_access_token(room_name: str, identity: str, name: str) -> str:
    """A LiveKit join token scoped to exactly one room."""
    settings = get_settings()
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )
