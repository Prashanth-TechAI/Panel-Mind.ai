"""PostgreSQL-backed stores.

Drop-in replacements for the JSON stores — the method surfaces match exactly, so
nothing above this module knows which one it is talking to.

Two things the JSON version could not do and this one does: append a single
utterance without rewriting the whole transcript, and serve more than one API
replica.
"""

from __future__ import annotations

import json
import time

from app.auth import AuthStore, OtpSender, User
from app.db import get_pool
from app.domain.daf import Daf
from app.domain.questions import MemberQuestionTree
from app.logging_setup import get_logger, new_id
from app.sessions import InterviewSession, Utterance


def _session_from_row(row, utterances: list[Utterance]) -> InterviewSession:
    return InterviewSession(
        id=row["id"],
        room_name=row["room_name"],
        daf=Daf.model_validate(json.loads(row["daf"])),
        trees=[MemberQuestionTree.model_validate(t) for t in json.loads(row["trees"])],
        preparation_failures=json.loads(row["preparation_failures"]),
        user_id=row["user_id"],
        created_at=row["created_at"],
        transcript=utterances,
        ended_reason=row["ended_reason"],
        marks=row["marks"],
    )


class PgSessionStore:
    """Prepared interviews in Postgres."""

    def __init__(self) -> None:
        self._log = get_logger(component="sessions.pg")

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

        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO sessions
                (id, room_name, user_id, daf, trees, preparation_failures, created_at)
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7)
            """,
            session.id,
            session.room_name,
            # A foreign key would reject an unknown id; anonymous mocks are allowed.
            user_id,
            json.dumps(daf.model_dump()),
            json.dumps([t.model_dump() for t in trees]),
            json.dumps(failures),
            session.created_at,
        )

        self._log.info(
            "interview session created",
            session_id=session.id,
            room=session.room_name,
            candidate=daf.full_name,
            prepared_members=session.prepared_members,
        )
        return session

    async def _load(self, where: str, value: str) -> InterviewSession | None:
        pool = await get_pool()
        row = await pool.fetchrow(f"SELECT * FROM sessions WHERE {where} = $1", value)
        if row is None:
            return None
        rows = await pool.fetch(
            "SELECT speaker, member_id, text, at_ms FROM utterances "
            "WHERE session_id = $1 ORDER BY id",
            row["id"],
        )
        return _session_from_row(row, [Utterance(**dict(r)) for r in rows])

    async def get(self, session_id: str) -> InterviewSession | None:
        return await self._load("id", session_id)

    async def get_by_room(self, room_name: str) -> InterviewSession | None:
        return await self._load("room_name", room_name)

    async def append_utterance(self, session_id: str, utterance: Utterance) -> None:
        # One row inserted, not a whole transcript rewritten.
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO utterances (session_id, speaker, member_id, text, at_ms) "
            "VALUES ($1, $2, $3, $4, $5)",
            session_id,
            utterance.speaker,
            utterance.member_id,
            utterance.text,
            utterance.at_ms,
        )

    async def for_user(self, user_id: str) -> list[InterviewSession]:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT s.*, COALESCE(u.n, 0) AS n FROM sessions s "
            "LEFT JOIN (SELECT session_id, COUNT(*) n FROM utterances GROUP BY session_id) u "
            "  ON u.session_id = s.id "
            "WHERE s.user_id = $1 ORDER BY s.created_at DESC",
            user_id,
        )
        # The list view needs the exchange count, not every line of dialogue.
        return [
            _session_from_row(r, [Utterance("", None, "", 0)] * r["n"]) for r in rows
        ]

    async def record_marks(self, session_id: str, marks: int) -> None:
        pool = await get_pool()
        await pool.execute("UPDATE sessions SET marks = $2 WHERE id = $1", session_id, marks)

    async def finish(self, session_id: str, reason: str) -> InterviewSession | None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE sessions SET ended_reason = $2 WHERE id = $1", session_id, reason
        )
        return await self.get(session_id)


class PgAuthStore(AuthStore):
    """Accounts in Postgres.

    Subclasses the JSON store to reuse the OTP logic — codes, hashing,
    throttling and lockout stay in memory on purpose, since a restart should
    invalidate any code already in flight. Only the durable part, the accounts,
    moves to Postgres.
    """

    def __init__(self, sender: OtpSender | None = None) -> None:
        super().__init__(sender=sender, path=None)
        self._log = get_logger(component="auth.pg")

    async def load_into_memory(self) -> int:
        """Warm the in-memory indexes at startup.

        The account set is small and the auth path is latency-sensitive, so it
        is held in memory and written through to Postgres.
        """
        pool = await get_pool()
        rows = await pool.fetch("SELECT * FROM users")
        for r in rows:
            self._index(
                User(
                    id=r["id"],
                    phone=r["phone"] or "",
                    email=r["email"] or "",
                    name=r["name"] or "",
                    created_at=r["created_at"],
                    mocks_taken=r["mocks_taken"],
                    last_seen_at=r["last_seen_at"],
                    email_verified=r["email_verified"],
                    phone_verified=r["phone_verified"],
                    whatsapp_opt_in=r["whatsapp_opt_in"],
                    has_avatar=r["avatar"] is not None,
                )
            )
        if rows:
            self._log.info(f"loaded {len(rows)} account(s) from postgres")
        return len(rows)

    async def ensure_persisted(self, user: User) -> None:
        """Write this one account and wait, so a dependent insert cannot race it."""
        pool = await get_pool()
        await pool.execute(
            """
            INSERT INTO users
                (id, phone, email, name, mocks_taken, created_at, last_seen_at,
                 email_verified, phone_verified, whatsapp_opt_in)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                phone = EXCLUDED.phone,
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                last_seen_at = EXCLUDED.last_seen_at,
                email_verified = EXCLUDED.email_verified,
                phone_verified = EXCLUDED.phone_verified,
                whatsapp_opt_in = EXCLUDED.whatsapp_opt_in
            """,
            user.id,
            user.phone or None,
            user.email or None,
            user.name,
            user.mocks_taken,
            user.created_at,
            user.last_seen_at,
            user.email_verified,
            user.phone_verified,
            user.whatsapp_opt_in,
        )

    def _persist(self) -> None:
        """Write-through. Fire-and-forget so sign-in never waits on the database."""
        import asyncio

        async def _write() -> None:
            pool = await get_pool()
            for u in list(self._users_by_id.values()):
                try:
                    await pool.execute(
                        """
                        INSERT INTO users
                            (id, phone, email, name, mocks_taken, created_at,
                             last_seen_at, email_verified, phone_verified,
                             whatsapp_opt_in)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (id) DO UPDATE SET
                            phone = EXCLUDED.phone,
                            email = EXCLUDED.email,
                            name = EXCLUDED.name,
                            mocks_taken = EXCLUDED.mocks_taken,
                            last_seen_at = EXCLUDED.last_seen_at,
                            email_verified = EXCLUDED.email_verified,
                            phone_verified = EXCLUDED.phone_verified,
                            whatsapp_opt_in = EXCLUDED.whatsapp_opt_in
                        """,
                        u.id,
                        # NULL rather than '' so the UNIQUE constraint does not
                        # collide two accounts that share a missing contact.
                        u.phone or None,
                        u.email or None,
                        u.name,
                        u.mocks_taken,
                        u.created_at,
                        u.last_seen_at,
                        u.email_verified,
                        u.phone_verified,
                        u.whatsapp_opt_in,
                    )
                except Exception as exc:
                    self._log.warning("could not persist account", error=str(exc))

        try:
            asyncio.get_running_loop().create_task(_write())
        except RuntimeError:
            # No loop (a synchronous test); the in-memory copy is still correct.
            pass


async def record_daf_upload(
    *,
    user_id: str | None,
    filename: str,
    content: bytes,
    pages: int,
    raw_fields: dict | None,
    parsed_daf: dict | None,
) -> str:
    """Keep the uploaded PDF and what was read from it.

    Storing the original means a bad OCR can be re-read later without asking the
    aspirant to upload their form again.
    """
    upload_id = new_id("daf")
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO daf_uploads
            (id, user_id, filename, content, pages, raw_fields, parsed_daf, created_at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
        """,
        upload_id,
        user_id,
        filename,
        content,
        pages,
        json.dumps(raw_fields) if raw_fields is not None else None,
        json.dumps(parsed_daf) if parsed_daf is not None else None,
        time.time(),
    )
    return upload_id


# --- The aspirant's own form ------------------------------------------------
#
# Kept against the account rather than against a session, so "Your DAF" has
# something to show before the first interview and still has it after.


async def save_daf_profile(
    *,
    user_id: str,
    source: str,
    form: dict | None = None,
    daf: dict | None = None,
    upload_id: str | None = None,
    filename: str | None = None,
) -> None:
    """Record what this aspirant has given the board. Latest wins."""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO daf_profiles
            (user_id, source, form, daf, upload_id, filename, updated_at)
        VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7)
        ON CONFLICT (user_id) DO UPDATE SET
            source     = EXCLUDED.source,
            form       = EXCLUDED.form,
            daf        = EXCLUDED.daf,
            upload_id  = EXCLUDED.upload_id,
            filename   = EXCLUDED.filename,
            updated_at = EXCLUDED.updated_at
        """,
        user_id,
        source,
        json.dumps(form) if form is not None else None,
        json.dumps(daf) if daf is not None else None,
        upload_id,
        filename,
        time.time(),
    )


async def get_daf_profile(user_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT source, form, daf, upload_id, filename, updated_at "
        "FROM daf_profiles WHERE user_id = $1",
        user_id,
    )
    if row is None:
        return None
    return {
        "source": row["source"],
        "form": json.loads(row["form"]) if row["form"] else None,
        "daf": json.loads(row["daf"]) if row["daf"] else None,
        "upload_id": row["upload_id"],
        "filename": row["filename"],
        "updated_at": row["updated_at"],
    }


async def get_daf_upload(upload_id: str) -> dict | None:
    """The stored PDF itself, for preview and download."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, user_id, filename, content, pages, raw_fields, created_at "
        "FROM daf_uploads WHERE id = $1",
        upload_id,
    )
    if row is None:
        return None
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "filename": row["filename"],
        "content": bytes(row["content"]),
        "pages": row["pages"],
        "raw_fields": json.loads(row["raw_fields"]) if row["raw_fields"] else {},
        "created_at": row["created_at"],
    }


async def save_avatar(user_id: str, content: bytes, mime: str) -> None:
    """The aspirant's photograph, stored beside the account."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET avatar = $2, avatar_type = $3 WHERE id = $1",
        user_id,
        content,
        mime,
    )


async def get_avatar(user_id: str) -> tuple[bytes, str] | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT avatar, avatar_type FROM users WHERE id = $1", user_id)
    if row is None or row["avatar"] is None:
        return None
    return bytes(row["avatar"]), row["avatar_type"] or "image/jpeg"


async def achievement_facts(user_id: str) -> dict:
    """Everything the awards are computed from. All of it measured, none guessed."""
    pool = await get_pool()

    row = await pool.fetchrow(
        """
        SELECT COUNT(*)                                        AS mocks,
               COUNT(*) FILTER (WHERE ended_reason IS NOT NULL) AS finished,
               COUNT(*) FILTER (WHERE ended_reason = 'interview_complete') AS completed,
               MAX(marks)                                      AS best_marks,
               AVG(marks)                                      AS average_marks,
               MIN(created_at)                                 AS first_at,
               MAX(created_at)                                 AS last_at
        FROM sessions WHERE user_id = $1
        """,
        user_id,
    )

    verdicts = await pool.fetch(
        """
        SELECT e.verdict, COUNT(*) AS n
        FROM exchanges e JOIN sessions s ON s.id = e.session_id
        WHERE s.user_id = $1 GROUP BY e.verdict
        """,
        user_id,
    )
    answered = await pool.fetchval(
        """
        SELECT COUNT(*) FROM utterances u JOIN sessions s ON s.id = u.session_id
        WHERE s.user_id = $1 AND u.member_id IS NULL
        """,
        user_id,
    )

    return {
        "mocks": row["mocks"] or 0,
        "finished": row["finished"] or 0,
        "completed": row["completed"] or 0,
        "best_marks": row["best_marks"],
        "average_marks": round(float(row["average_marks"]), 1) if row["average_marks"] else None,
        "first_at": row["first_at"],
        "last_at": row["last_at"],
        "answers_given": answered or 0,
        "verdicts": {r["verdict"]: r["n"] for r in verdicts if r["verdict"]},
    }
