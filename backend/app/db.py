"""PostgreSQL connection and schema.

A local Postgres, one connection pool for the process. asyncpg rather than a
sync driver because the whole control plane is async and writes happen on the
interview's critical path.

If ``DATABASE_URL`` is unset or the server is unreachable the application falls
back to the on-disk JSON stores, so a fresh checkout and the test suite work
without a database.
"""

from __future__ import annotations

import asyncpg

from app.config import get_settings
from app.logging_setup import get_logger

_pool: asyncpg.Pool | None = None
_log = get_logger(component="db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    phone         TEXT UNIQUE,
    email         TEXT UNIQUE,
    name          TEXT NOT NULL DEFAULT '',
    mocks_taken   INTEGER NOT NULL DEFAULT 0,
    created_at    DOUBLE PRECISION NOT NULL,
    last_seen_at  DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                   TEXT PRIMARY KEY,
    room_name            TEXT UNIQUE NOT NULL,
    user_id              TEXT REFERENCES users(id) ON DELETE SET NULL,
    daf                  JSONB NOT NULL,
    trees                JSONB NOT NULL DEFAULT '[]'::jsonb,
    preparation_failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    ended_reason         TEXT,
    marks                INTEGER,
    created_at           DOUBLE PRECISION NOT NULL
);

-- `My mocks` lists a candidate's attempts newest first.
CREATE INDEX IF NOT EXISTS sessions_user_recent ON sessions (user_id, created_at DESC);

-- One row per exchange, so an utterance is an INSERT rather than a rewrite of
-- the whole transcript.
CREATE TABLE IF NOT EXISTS utterances (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    speaker    TEXT NOT NULL,
    member_id  TEXT,
    text       TEXT NOT NULL,
    at_ms      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS utterances_session ON utterances (session_id, id);

-- One row per question-and-answer, judged while it is fresh.
--
-- Scoring is still a batch pass, but it reads these rows instead of
-- re-deriving every judgement from the transcript at the end. That also means
-- a failed final evaluation no longer loses the signal.
CREATE TABLE IF NOT EXISTS exchanges (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn        INTEGER NOT NULL,
    member_id   TEXT NOT NULL,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    -- answered | evasive | bluffed | admitted_ignorance | non_answer
    verdict     TEXT,
    note        TEXT,
    created_at  DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS exchanges_session ON exchanges (session_id, turn);

-- The uploaded DAF, kept so a bad OCR can be re-read without asking the
-- aspirant to upload again.
CREATE TABLE IF NOT EXISTS daf_uploads (
    id          TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
    filename    TEXT NOT NULL,
    content     BYTEA NOT NULL,
    pages       INTEGER NOT NULL DEFAULT 0,
    raw_fields  JSONB,
    parsed_daf  JSONB,
    created_at  DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS daf_uploads_user ON daf_uploads (user_id, created_at DESC);

-- Columns added after the table first shipped. CREATE TABLE IF NOT EXISTS
-- will not add them to an existing database, so they are stated separately.
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified  BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified  BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar          BYTEA;
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_type     TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS whatsapp_opt_in BOOLEAN NOT NULL DEFAULT FALSE;

-- The aspirant's current form, one row per account.
--
-- A DAF used to exist only inside whichever session it was convened for, so
-- "Your DAF" had nothing to show until an interview had been sat, and a typed
-- form was lost the moment the tab closed. It belongs to the person.
--
-- ``source`` decides what that page renders: 'upload' shows the PDF they gave
-- us, 'form' shows the fields they typed and offers to print them as one.
CREATE TABLE IF NOT EXISTS daf_profiles (
    user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    -- The typed form exactly as entered, so it can be shown back and edited.
    form        JSONB,
    -- The validated Daf the board is briefed from.
    daf         JSONB,
    -- For an upload: which row in daf_uploads holds the original bytes.
    upload_id   TEXT REFERENCES daf_uploads(id) ON DELETE SET NULL,
    filename    TEXT,
    updated_at  DOUBLE PRECISION NOT NULL
);
"""


def is_configured() -> bool:
    return bool(get_settings().database_url)


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            get_settings().database_url,
            min_size=1,
            max_size=10,
            command_timeout=10,
        )
    return _pool


async def ping() -> tuple[bool, str]:
    """Confirm the server answers. Returns (ok, detail)."""
    try:
        pool = await get_pool()
        version = await pool.fetchval("SELECT version()")
    except Exception as exc:
        return False, str(exc)[:200]
    return True, version.split(",")[0]


async def ensure_schema() -> None:
    """Create tables and indexes. Idempotent — safe on every startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
    _log.info("postgres schema ensured")


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
