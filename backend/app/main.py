"""FastAPI application.

Hosts the control plane: health, board metadata, DAF intake and (later) the
evaluator pipeline. The live voice worker is a separate LiveKit process; it
talks to this API for conductor decisions and stores its transcript here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from typing import Literal

from pydantic import BaseModel, Field

from app.auth import (
    AuthError,
    CompleteProfileRequest,
    StartRequest,
    User,
    VerifyRequest,
    public_user,
)
from app.auth import store as json_auth_store
from app import db
from app.config import get_settings
from app.domain.board import BOARD, MEMBER_IDS, TRAIT_LABELS, MemberId, get_member
from app.domain.daf import Daf, to_portfolios
from app.domain.evaluation import Utterance as EvalUtterance
from app.domain.evaluation import evaluate_interview
from app.domain.questions import generate_all_trees
from app.sessions import Utterance, mint_access_token
from app.sessions import store as json_store
from app.logging_setup import configure_logging, get_logger, new_id
from app.providers.health import probe_all
from app.providers.tts import synthesize


# Swapped for the Mongo-backed stores at startup when a URI is configured.
# Everything below refers to these names, so nothing else has to know which.
store = json_store
auth_store = json_auth_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global store, auth_store

    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger(component="startup")

    # --- Storage: MongoDB when configured, on-disk JSON otherwise ---
    if db.is_configured():
        ok, detail = await db.ping()
        if ok:
            from app.stores_pg import PgAuthStore, PgSessionStore

            await db.ensure_schema()
            store = PgSessionStore()
            auth_store = PgAuthStore(sender=json_auth_store.sender)
            await auth_store.load_into_memory()
            log.info(f"storage: PostgreSQL — {detail}", storage="postgres")
        else:
            log.error(
                "DATABASE_URL is set but Postgres is unreachable — falling back to JSON",
                error=detail,
            )
    else:
        log.info("storage: on-disk JSON (set DATABASE_URL to use Postgres)", storage="json")

    log.info(
        "UPSC board API starting",
        environment=settings.environment,
        tts_chain=settings.tts_chain,
        hot_model=settings.groq_model,
        cold_model=settings.openrouter_model,
    )
    yield
    await db.close()
    get_logger(component="shutdown").info("UPSC board API stopped")


app = FastAPI(
    title="UPSC Interview Board",
    description="Five AI board members interview and score one candidate.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Tts-Provider", "X-Tts-Ttfb-Ms", "X-Tts-Fell-Back-From", "X-Member-Name"],
)


@app.middleware("http")
async def correlate_requests(request: Request, call_next):
    """Stamp every request with an id so its logs can be pulled together."""
    request_id = new_id("req")
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# --- Authentication ---------------------------------------------------------


def current_user(request: Request) -> User | None:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else None
    # A PDF shown in an <iframe> or opened by "Download" is fetched by the
    # browser itself, which sends no Authorization header. Those routes accept
    # the same token in the query string instead.
    if token is None:
        token = request.query_params.get("token")
    return auth_store.user_from_token(token)


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise AuthError("Please sign in.", status=401)
    return user


@app.exception_handler(AuthError)
async def _auth_error(_request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=exc.status)


@app.post("/api/auth/start")
async def auth_start(body: StartRequest) -> JSONResponse:
    """Send a sign-in code. The identifier may be a phone number or an email.

    There is no password anywhere in the system — a one-time code is the only
    way in, by either channel.
    """
    return JSONResponse(await auth_store.start_login(body.identifier))


@app.post("/api/auth/verify")
async def auth_verify(body: VerifyRequest) -> JSONResponse:
    """Exchange a code for a session.

    ``needs_profile`` tells the client to collect the name plus whichever
    contact detail sign-in did not supply — asked once, never again.
    """
    user, token, is_new = await auth_store.verify(body.identifier, body.code)
    return JSONResponse(
        {
            "token": token,
            "user": public_user(user),
            "is_new": is_new,
            "needs_profile": not user.is_complete,
            # Tells the client which field to ask for.
            "missing": [
                field
                for field, value in (("email", user.email), ("phone", user.phone))
                if not value
            ],
        }
    )


@app.post("/api/auth/profile")
async def auth_profile(body: CompleteProfileRequest, request: Request) -> JSONResponse:
    user = require_user(request)
    auth_store.complete_profile(
        user,
        body.name,
        email=str(body.email) if body.email else None,
        phone=body.phone,
    )
    return JSONResponse({"user": public_user(user)})


@app.get("/api/auth/me")
async def auth_me(request: Request) -> JSONResponse:
    user = require_user(request)
    return JSONResponse({"user": public_user(user)})


class UpdateProfileRequest(BaseModel):
    """Editing the account. Every field optional — send only what changed."""

    name: str | None = Field(default=None, min_length=2, max_length=80)
    email: str | None = None
    phone: str | None = None


class VerifyContactRequest(BaseModel):
    channel: Literal["phone", "email"]
    code: str | None = None


class WhatsappRequest(BaseModel):
    opt_in: bool


@app.get("/api/me/profile")
async def my_profile(request: Request) -> JSONResponse:
    """Everything the profile page shows: the account, and what it has earned."""
    user = require_user(request)
    log = get_logger(component="api.me.profile")

    from app.domain.achievements import summarise
    from app.providers import whatsapp

    facts: dict = {}
    if db.is_configured():
        try:
            from app.stores_pg import achievement_facts

            facts = await achievement_facts(user.id)
        except Exception as exc:
            log.warning("could not read achievement facts", error=str(exc))

    awards = summarise(facts)
    log.info(
        "served the profile",
        awards_held=awards["held"],
        mocks=awards["stats"]["mocks"],
        phone_verified=user.phone_verified,
        email_verified=user.email_verified,
    )

    return JSONResponse(
        {
            "user": public_user(user),
            **awards,
            "whatsapp": {
                "opt_in": user.whatsapp_opt_in,
                # Whether this deployment can actually send. The page says so
                # rather than offering a button that quietly does nothing.
                "sending_configured": whatsapp.is_configured(),
                "business_number": whatsapp.business_number(),
                "link": whatsapp.opt_in_link(),
            },
        }
    )


@app.patch("/api/me/profile")
async def update_my_profile(request: Request, body: UpdateProfileRequest) -> JSONResponse:
    """Change the name, the email or the mobile number.

    A changed contact loses its verified badge until its own code comes back —
    handled in the store, not here.
    """
    user = require_user(request)
    log = get_logger(component="api.me.profile")

    auth_store.complete_profile(
        user,
        body.name if body.name is not None else user.name,
        email=body.email or None,
        phone=body.phone or None,
    )
    log.info("profile updated", user_id=user.id)
    return JSONResponse({"user": public_user(user)})


@app.post("/api/me/verify/start")
async def start_verification(request: Request, body: VerifyContactRequest) -> JSONResponse:
    """Send a one-time code to whichever contact is not yet verified."""
    user = require_user(request)
    return JSONResponse(await auth_store.start_contact_verification(user, body.channel))


@app.post("/api/me/verify/confirm")
async def confirm_verification(request: Request, body: VerifyContactRequest) -> JSONResponse:
    user = require_user(request)
    if not body.code:
        raise AuthError("Enter the code.", status=400)
    auth_store.confirm_contact(user, body.channel, body.code)
    return JSONResponse({"user": public_user(user)})


@app.put("/api/me/whatsapp")
async def set_whatsapp(request: Request, body: WhatsappRequest) -> JSONResponse:
    """Turn updates on WhatsApp on or off, and confirm what that means."""
    user = require_user(request)
    from app.providers import whatsapp

    auth_store.set_whatsapp(user, body.opt_in)

    # Opting in sends the confirmation itself, so the aspirant sees the channel
    # work rather than taking our word for it.
    result: dict = {"sent": False}
    if body.opt_in:
        result = await whatsapp.send_text(
            user.phone,
            "PanelMind AI: updates are on. You will get your board's verdict "
            "and your marks here as soon as they are ready. Reply STOP to turn "
            "this off.",
        )

    return JSONResponse(
        {
            "user": public_user(user),
            "opt_in": user.whatsapp_opt_in,
            "confirmation": result,
            "sending_configured": whatsapp.is_configured(),
            "link": whatsapp.opt_in_link(),
        }
    )


@app.post("/api/me/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """A photograph for the account."""
    user = require_user(request)
    log = get_logger(component="api.me.avatar")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise AuthError("That image is too large. Keep it under 5 MB.", status=413)
    if not (file.content_type or "").startswith("image/"):
        raise AuthError("That is not an image.", status=415)
    if not db.is_configured():
        raise AuthError("No database configured.", status=503)

    from app.stores_pg import save_avatar

    await auth_store.ensure_persisted(user)
    await save_avatar(user.id, content, file.content_type or "image/jpeg")
    auth_store.set_avatar_flag(user, True)
    log.info("avatar saved", bytes=len(content), mime=file.content_type)
    return JSONResponse({"user": public_user(user)})


@app.get("/api/me/avatar")
async def read_avatar(request: Request) -> Response:
    user = require_user(request)
    if not db.is_configured():
        raise AuthError("No photograph on file.", status=404)

    from app.stores_pg import get_avatar

    found = await get_avatar(user.id)
    if found is None:
        raise AuthError("No photograph on file.", status=404)

    content, mime = found
    return Response(content=content, media_type=mime, headers={"Cache-Control": "no-cache"})


@app.get("/api/me/mocks")
async def my_mocks(request: Request) -> JSONResponse:
    """Every interview this aspirant has sat, newest first."""
    user = require_user(request)
    mocks = await store.for_user(user.id)

    return JSONResponse(
        {
            "mocks": [
                {
                    "session_id": s.id,
                    "candidate": s.daf.full_name,
                    "optional_subject": s.daf.optional_subject,
                    "home_district": s.daf.home_district,
                    "created_at": s.created_at,
                    "exchanges": len(s.transcript),
                    "ended_reason": s.ended_reason,
                    "marks": s.marks,
                    "sat": bool(s.transcript),
                }
                for s in mocks
            ]
        }
    )


@app.post("/api/daf/upload")
async def upload_daf(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """Read a scanned DAF PDF.

    The original file and the raw reading are both kept, so a bad parse can be
    re-run later without asking the aspirant to upload their form again. The
    result is always returned for review — OCR is never trusted silently.
    """
    from app.domain.daf_pdf import DafParseError, read_pdf, to_daf

    log = get_logger(component="api.daf.upload")
    user = current_user(request)
    content = await file.read()

    try:
        raw_fields, extracted = await read_pdf(log, content)
    except DafParseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception as exc:
        log.error("could not read the uploaded DAF", error=str(exc))
        return JSONResponse(
            {"error": "That form could not be read. You can fill it in by hand instead."},
            status_code=503,
        )

    daf, missing = to_daf(extracted)

    try:
        from app.domain.daf_pdf import PdfReader_from_bytes

        page_count = len(PdfReader_from_bytes(content).pages)
    except Exception:
        page_count = 0

    if db.is_configured():
        from app.stores_pg import record_daf_upload, save_daf_profile

        try:
            if user:
                await auth_store.ensure_persisted(user)
            upload_id = await record_daf_upload(
                user_id=user.id if user else None,
                filename=file.filename or "daf.pdf",
                content=content,
                pages=page_count,
                raw_fields=raw_fields,
                parsed_daf=daf.model_dump() if daf else None,
            )
            # This is now their form on file, so "Your DAF" shows the PDF back
            # rather than our reading of it.
            if user:
                await save_daf_profile(
                    user_id=user.id,
                    source="upload",
                    daf=daf.model_dump() if daf else None,
                    upload_id=upload_id,
                    filename=file.filename or "daf.pdf",
                )
        except Exception as exc:
            # Losing the archive copy must not lose the aspirant's parse.
            log.warning("could not archive the upload", error=str(exc))

    log.info(
        "DAF read",
        candidate=extracted.full_name or "(unreadable)",
        raw_fields=len(raw_fields),
        complete=daf is not None,
        missing=missing,
    )

    return JSONResponse(
        {
            "complete": daf is not None,
            "daf": daf.model_dump() if daf else extracted.model_dump(),
            "missing": missing,
            "fields_read": len(raw_fields),
            # What the form actually said, label by label. The review shows
            # this rather than our schema, because squeezing 194 fields into
            # 30 slots invents gaps that were never in the aspirant's DAF.
            "raw_fields": raw_fields,
        }
    )


@app.post("/api/session/from-upload")
async def session_from_upload(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """Convene a board straight from an uploaded DAF.

    The form is not mapped onto our schema — every field it carries is handed to
    the members as-is, so nothing is discarded. This is the path an aspirant
    with a PDF should take; the typed form is for those without one.
    """
    from app.domain.daf_pdf import DafParseError, page_images, read_pdf
    from app.domain.questions import generate_trees_from_portfolios
    from app.domain.raw_daf import candidate_name, portfolios_from_raw

    log = get_logger(component="api.session.upload")
    user = current_user(request)
    content = await file.read()

    try:
        raw_fields, _extracted = await read_pdf(log, content)
    except DafParseError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)
    except Exception as exc:
        log.error("could not read the uploaded DAF", error=str(exc))
        return JSONResponse(
            {"error": "That form could not be read. You can fill it in by hand instead."},
            status_code=503,
        )

    candidate = candidate_name(raw_fields)
    portfolios = await portfolios_from_raw(raw_fields)
    trees, failures = await generate_trees_from_portfolios(portfolios, candidate)

    if not trees:
        return JSONResponse(
            {"error": "The board could not prepare from that form.", "failures": failures},
            status_code=503,
        )

    # A Daf is still stored so the evaluators and the room have a name to use;
    # the questions themselves came from the whole form.
    daf = Daf.model_validate(
        {
            "full_name": candidate,
            "home_state": raw_fields.get("State") or "Not stated",
            "home_district": raw_fields.get("District") or "Not stated",
            "education": {"graduation_subject": "See form", "graduation_college": "See form"},
            "optional_subject": raw_fields.get("11. (b) Optional Subject for paper VI & VII")
            or "See form",
            "hobbies": ["See form"],
            "service_preference": ["See form"],
        }
    )

    session = await store.create(daf, trees, failures, user_id=user.id if user else None)
    if user is not None:
        auth_store.record_mock(user.id)

    if db.is_configured():
        from app.stores_pg import record_daf_upload

        try:
            await record_daf_upload(
                user_id=user.id if user else None,
                filename=file.filename or "daf.pdf",
                content=content,
                pages=len(page_images(content)),
                raw_fields=raw_fields,
                parsed_daf=None,
            )
        except Exception as exc:
            log.warning("could not archive the upload", error=str(exc))

    log.info(
        "board convened from an uploaded form",
        candidate=candidate,
        fields=len(raw_fields),
        questions=sum(len(n.follow_ups) + 1 for t in trees for n in t.nodes),
    )

    return JSONResponse(
        {
            "session_id": session.id,
            "room": session.room_name,
            "token": mint_access_token(session.room_name, "candidate", candidate),
            "livekit_url": get_settings().livekit_url,
            "candidate": candidate,
            "fields_used": len(raw_fields),
            "prepared_members": session.prepared_members,
            "failures": failures,
            "total_questions": sum(len(n.follow_ups) + 1 for t in trees for n in t.nodes),
        }
    )


class SaveDafRequest(BaseModel):
    """The typed form exactly as entered, kept so it can be shown back."""

    form: dict
    daf: dict | None = None


@app.get("/api/me/daf")
async def my_daf(request: Request) -> JSONResponse:
    """The aspirant's form: which way they gave it, and everything in it.

    Backs both the menu line and the "Your DAF" page. An upload returns the
    labels the scan actually read, in the form's own words; a typed form
    returns the fields as entered.
    """
    user = require_user(request)
    log = get_logger(component="api.me.daf")

    if db.is_configured():
        from app.stores_pg import get_daf_profile, get_daf_upload

        profile = await get_daf_profile(user.id)
        if profile:
            body: dict = {
                "has_daf": True,
                "source": profile["source"],
                "updated_at": profile["updated_at"],
                "form": profile["form"] or {},
                "candidate": (profile["form"] or {}).get("full_name", ""),
            }
            if profile["source"] == "upload" and profile["upload_id"]:
                upload = await get_daf_upload(profile["upload_id"])
                if upload:
                    body |= {
                        "filename": upload["filename"],
                        "pages": upload["pages"],
                        "fields_read": len(upload["raw_fields"]),
                        "raw_fields": upload["raw_fields"],
                        "candidate": body["candidate"] or upload["raw_fields"].get("Name", ""),
                    }
            log.info(
                "served the aspirant's form",
                source=body["source"],
                fields=len(body.get("raw_fields") or body["form"]),
            )
            return JSONResponse(body)

    # Nothing saved against the account. Anyone who convened a board before
    # this existed still has their form inside that session.
    mocks = await store.for_user(user.id)
    if not mocks:
        return JSONResponse({"has_daf": False, "source": None})

    latest = mocks[0]
    return JSONResponse(
        {
            "has_daf": True,
            "source": "form",
            "candidate": latest.daf.full_name,
            "updated_at": latest.created_at,
            "form": {},
        }
    )


@app.put("/api/me/daf")
async def save_my_daf(request: Request, body: SaveDafRequest) -> JSONResponse:
    """Keep a typed form against the account, so "Your DAF" can show it back."""
    user = require_user(request)
    log = get_logger(component="api.me.daf")

    if not db.is_configured():
        return JSONResponse({"saved": False, "reason": "no database configured"})

    from app.stores_pg import save_daf_profile

    await auth_store.ensure_persisted(user)
    await save_daf_profile(user_id=user.id, source="form", form=body.form, daf=body.daf)
    log.info("saved a typed form", fields=len([v for v in body.form.values() if v]))
    return JSONResponse({"saved": True, "source": "form"})


@app.get("/api/me/daf/file")
async def my_daf_file(request: Request, download: int = Query(0, ge=0, le=1)) -> Response:
    """The PDF the aspirant uploaded, byte for byte.

    Inline by default so it can be previewed in the page; ``?download=1``
    makes the browser save it instead.
    """
    user = require_user(request)

    if not db.is_configured():
        raise AuthError("No form on file.", status=404)

    from app.stores_pg import get_daf_profile, get_daf_upload

    profile = await get_daf_profile(user.id)
    if not profile or profile["source"] != "upload" or not profile["upload_id"]:
        raise AuthError("You have not uploaded a form.", status=404)

    upload = await get_daf_upload(profile["upload_id"])
    if upload is None or upload["user_id"] != user.id:
        raise AuthError("No form on file.", status=404)

    name = upload["filename"] or "daf.pdf"
    disposition = "attachment" if download else "inline"
    return Response(
        content=upload["content"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{name}"'},
    )


@app.get("/api/me/daf/export")
async def export_my_daf(request: Request, download: int = Query(1, ge=0, le=1)) -> Response:
    """A typed form printed as a UPSC DAF-I — the Commission's own layout."""
    user = require_user(request)
    log = get_logger(component="api.me.daf.export")

    if not db.is_configured():
        raise AuthError("No form on file.", status=404)

    from app.domain.daf_export import build_daf_pdf
    from app.stores_pg import get_daf_profile

    profile = await get_daf_profile(user.id)
    form = (profile or {}).get("form") or {}
    if not form:
        raise AuthError("Fill in your form before exporting it.", status=404)

    pdf = build_daf_pdf(form, email=user.email or "", phone=user.phone or "")
    log.info("printed a DAF-I", bytes=len(pdf), candidate=form.get("full_name", ""))

    stem = (form.get("full_name") or "candidate").strip().upper().replace(" ", "_")
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{stem}_DAF_1.pdf"'},
    )


@app.get("/api/health")
async def health(deep: int = Query(0, ge=0, le=1)) -> JSONResponse:
    """Auth-level probe of every provider; ``?deep=1`` also verifies TTS quota.

    Returns 200 when everything is ok and 503 otherwise, so it can back a
    container readiness probe directly.
    """
    log = get_logger(component="api.health")

    try:
        report = await probe_all(deep=bool(deep))
    except Exception as exc:
        # A throw here means config validation failed — the process is
        # misconfigured, not merely a provider being down.
        log.error("health check could not run", error=str(exc))
        return JSONResponse({"status": "down", "error": str(exc)}, status_code=503)

    log.info(f"health check -> {report.status}", status=report.status, total_ms=report.total_ms)
    return JSONResponse(asdict(report), status_code=503 if report.status == "down" else 200)


@app.get("/api/board")
async def board() -> dict:
    """The five members, for the UI to render nameplates and voice previews."""
    return {
        "members": [
            {
                "id": m.id,
                "name": m.name,
                "title": m.title,
                "role": m.role,
                "owns": list(m.owns),
                "weighs": list(m.weighs),
                "accent": m.accent,
            }
            for m in BOARD
        ],
        "traits": [{"key": k, "label": v} for k, v in TRAIT_LABELS.items()],
    }


@app.post("/api/daf")
async def submit_daf(daf: Daf) -> dict:
    """Validate a DAF and return how the board will divide it.

    Returning the split immediately is deliberate: the candidate sees exactly
    which member owns which part of their form before the interview starts,
    which is both reassuring and a fair warning.
    """
    log = get_logger(component="api.daf")
    portfolios = to_portfolios(daf)

    log.info(
        "DAF accepted",
        candidate=daf.full_name,
        home=f"{daf.home_district}, {daf.home_state}",
        optional=daf.optional_subject,
        attempt=daf.attempt_number,
        sections=sum(len(p.sections) for p in portfolios),
    )

    return {
        "accepted": True,
        "candidate": daf.full_name,
        "portfolios": [
            {
                "member_id": p.member_id,
                "member_name": p.member_name,
                "sections": [
                    {"field": s.field, "label": s.label, "content": s.content}
                    for s in p.sections
                ],
            }
            for p in portfolios
        ],
    }


@app.post("/api/questions")
async def prepare_questions(daf: Daf) -> JSONResponse:
    """Pre-generate every member's question tree from the DAF.

    Slow and deliberate — this runs once, before the interview. Doing it here
    is what lets a live turn merely rephrase a prepared node instead of
    inventing a question, which is the difference between a 200ms turn and a
    two-second one.
    """
    log = get_logger(component="api.questions")

    trees, failures = await generate_all_trees(daf)

    if not trees:
        log.error("no member could prepare questions", failures=failures)
        return JSONResponse(
            {
                "error": "The board could not prepare. No member produced questions.",
                "failures": failures,
            },
            status_code=503,
        )

    return JSONResponse(
        {
            "candidate": daf.full_name,
            "trees": [t.model_dump() for t in trees],
            "prepared": len(trees),
            "total_questions": sum(
                len(n.follow_ups) + 1 for t in trees for n in t.nodes
            ),
            # A member who failed to prepare is skipped, not fatal. Say so.
            "failures": failures,
        }
    )


@app.post("/api/session")
async def create_session(daf: Daf, request: Request) -> JSONResponse:
    """Prepare an interview and hand back the credentials to join it.

    Everything slow happens here — question generation across five members —
    so that once the candidate is in the room, every turn is fast.
    """
    log = get_logger(component="api.session")

    trees, failures = await generate_all_trees(daf)
    if not trees:
        log.error("board could not prepare", failures=failures)
        return JSONResponse(
            {"error": "The board could not prepare for this interview.", "failures": failures},
            status_code=503,
        )

    # Sign-in is optional while in preview: anyone may sit a mock. A signed-in
    # aspirant gets it filed against their account so it shows up in My mocks;
    # an anonymous one still gets the full interview and scorecard.
    user = current_user(request)
    session = await store.create(daf, trees, failures, user_id=user.id if user else None)
    if user is not None:
        auth_store.record_mock(user.id)
    token = mint_access_token(session.room_name, identity="candidate", name=daf.full_name)

    return JSONResponse(
        {
            "session_id": session.id,
            "room": session.room_name,
            "token": token,
            "livekit_url": get_settings().livekit_url,
            "prepared_members": session.prepared_members,
            # A member who could not prepare is skipped, not fatal. Say so.
            "failures": failures,
            "total_questions": sum(len(n.follow_ups) + 1 for t in trees for n in t.nodes),
        }
    )


@app.get("/api/session/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    """Session material. The voice worker calls this when it joins the room."""
    session = await store.get(session_id)
    if session is None:
        return JSONResponse({"error": f"Unknown session '{session_id}'"}, status_code=404)

    return JSONResponse(
        {
            "session_id": session.id,
            "room": session.room_name,
            "daf": session.daf.model_dump(),
            "trees": [t.model_dump() for t in session.trees],
            "ended_reason": session.ended_reason,
            "transcript": [
                {
                    "speaker": u.speaker,
                    "member_id": u.member_id,
                    "text": u.text,
                    "at_ms": u.at_ms,
                }
                for u in session.transcript
            ],
        }
    )


@app.get("/api/session/by-room/{room_name}")
async def get_session_by_room(room_name: str) -> JSONResponse:
    """Room-name lookup, so the worker can resolve a session from its job."""
    session = await store.get_by_room(room_name)
    if session is None:
        return JSONResponse({"error": f"No session for room '{room_name}'"}, status_code=404)
    return await get_session(session.id)


class ExchangeIn(BaseModel):
    turn: int
    member_id: str
    question: str
    answer: str
    verdict: str | None = None
    note: str | None = None


@app.post("/api/session/{session_id}/exchange")
async def record_exchange(session_id: str, body: ExchangeIn) -> JSONResponse:
    """Bank one judged question-and-answer as the interview runs."""
    if not db.is_configured():
        return JSONResponse({"recorded": False, "reason": "no database"})

    import time as _time

    pool = await db.get_pool()
    await pool.execute(
        """
        INSERT INTO exchanges
            (session_id, turn, member_id, question, answer, verdict, note, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        session_id, body.turn, body.member_id, body.question,
        body.answer, body.verdict, body.note, _time.time(),
    )
    return JSONResponse({"recorded": True})


@app.get("/api/session/{session_id}/exchanges")
async def list_exchanges(session_id: str) -> JSONResponse:
    """Everything banked so far, for the batch scoring pass to read."""
    if not db.is_configured():
        return JSONResponse({"exchanges": []})

    pool = await db.get_pool()
    rows = await pool.fetch(
        "SELECT turn, member_id, question, answer, verdict, note "
        "FROM exchanges WHERE session_id = $1 ORDER BY turn",
        session_id,
    )
    return JSONResponse({"exchanges": [dict(r) for r in rows]})


class UtteranceIn(BaseModel):
    speaker: str
    member_id: str | None = None
    text: str
    at_ms: int = 0


@app.post("/api/session/{session_id}/transcript")
async def append_transcript(session_id: str, utterance: UtteranceIn) -> JSONResponse:
    """Record one exchange. Called by the voice worker as the interview runs.

    Written incrementally rather than in one batch at the end so a worker crash
    costs the tail of the transcript, not the whole thing.
    """
    session = await store.get(session_id)
    if session is None:
        return JSONResponse({"error": f"Unknown session '{session_id}'"}, status_code=404)

    await store.append_utterance(
        session_id,
        Utterance(
            speaker=utterance.speaker,
            member_id=utterance.member_id,
            text=utterance.text,
            at_ms=utterance.at_ms,
        ),
    )
    return JSONResponse({"recorded": True, "exchanges": len(session.transcript) + 1})


@app.post("/api/session/{session_id}/end")
async def end_session(session_id: str, reason: str = Query("interview_complete")) -> JSONResponse:
    session = await store.finish(session_id, reason)
    if session is None:
        return JSONResponse({"error": f"Unknown session '{session_id}'"}, status_code=404)

    get_logger(component="api.session").info(
        "interview ended",
        session_id=session_id,
        reason=reason,
        exchanges=len(session.transcript),
    )
    return JSONResponse({"ended": True, "reason": reason, "exchanges": len(session.transcript)})


@app.post("/api/session/{session_id}/evaluate")
async def evaluate(session_id: str) -> JSONResponse:
    """Score a finished interview.

    Five evaluators read the same transcript through five different lenses and
    never see each other's verdicts. Slow and off the critical path by design.
    """
    log = get_logger(component="api.evaluate", session_id=session_id)

    session = await store.get(session_id)
    if session is None:
        return JSONResponse({"error": f"Unknown session '{session_id}'"}, status_code=404)

    if not session.transcript:
        return JSONResponse(
            {
                "error": "There is nothing to score — no exchanges were recorded.",
                "hint": "The interview must be sat before it can be marked.",
            },
            status_code=409,
        )

    transcript = [
        EvalUtterance(
            speaker=u.speaker, member_id=u.member_id, text=u.text, at_ms=u.at_ms
        )
        for u in session.transcript
    ]

    # Verdicts banked during the interview. The batch pass reads these rather
    # than re-deriving every judgement, so a bluff caught in the room is the
    # same bluff that appears on the scorecard.
    banked: list[dict] = []
    if db.is_configured():
        try:
            pool = await db.get_pool()
            rows = await pool.fetch(
                "SELECT turn, member_id, question, answer, verdict, note "
                "FROM exchanges WHERE session_id = $1 ORDER BY turn",
                session_id,
            )
            banked = [dict(r) for r in rows]
        except Exception as exc:
            log.warning("could not read banked exchanges", error=str(exc))

    log.info(
        "evaluating",
        exchanges=len(transcript),
        banked_verdicts=len(banked),
        bluffs=sum(1 for b in banked if b["verdict"] == "bluffed"),
        admitted=sum(1 for b in banked if b["verdict"] == "admitted_ignorance"),
    )

    try:
        report = await evaluate_interview(session.daf, transcript, banked=banked)
    except Exception as exc:
        log.error("evaluation failed", error=str(exc))
        return JSONResponse(
            {"error": "The board could not produce a scorecard.", "detail": str(exc)},
            status_code=503,
        )

    # Cache the mark so the dashboard and progress chart never re-evaluate.
    await store.record_marks(session_id, report.consolidated_marks)

    return JSONResponse(report.model_dump())


@app.get("/api/tts/preview")
async def tts_preview(
    member: str = Query("M0"),
    text: str | None = Query(None),
):
    """Stream one board member speaking.

    Backs the voice preview in the UI, and gives the e2e suite a way to prove
    that failover produces real audio rather than merely logging that it would.
    """
    if member not in MEMBER_IDS:
        return JSONResponse(
            {"error": f"Unknown member '{member}'. Expected one of {', '.join(MEMBER_IDS)}."},
            status_code=400,
        )

    member_id: MemberId = member  # type: ignore[assignment]
    board_member = get_member(member_id)
    line = (text or f"I am the {board_member.title}. Let us begin.")[:500]

    log = get_logger(component="api.tts.preview", member_id=member_id)

    try:
        result = await synthesize(log, member_id, line)
    except Exception as exc:
        log.error("every TTS provider failed", error=str(exc))
        return JSONResponse(
            {
                "error": "The board cannot speak — every TTS provider failed.",
                "detail": str(exc),
            },
            status_code=503,
        )

    log.info(
        f"spoke as {board_member.name} via {result.provider} (TTFB {result.ttfb_ms}ms)",
        provider=result.provider,
        ttfb_ms=result.ttfb_ms,
        fell_back_from=result.fell_back_from,
    )

    return StreamingResponse(
        result.chunks,
        media_type=result.content_type,
        headers={
            "Cache-Control": "no-store",
            # Surfaced as headers so the UI and the e2e suite can assert on which
            # provider actually spoke without parsing the audio.
            "X-Tts-Provider": result.provider,
            "X-Tts-Ttfb-Ms": str(result.ttfb_ms),
            "X-Tts-Fell-Back-From": ",".join(result.fell_back_from) or "none",
            "X-Member-Name": board_member.name,
        },
    )
