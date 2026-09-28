"""Reading a DAF out of an uploaded PDF.

Real DAFs are scanned — the sample from an actual aspirant had eight pages and
zero extractable text. So this does not parse text; it reads the pages as
images with a vision model, the same way a person would.

The extraction is deliberately two-stage:

  1. Read every visible label and value verbatim, whatever the form says.
  2. Map those onto our own schema.

Keeping them apart means the raw reading is preserved even when our mapping is
wrong or the form's layout changes, so a bad parse can be re-run later without
asking the aspirant to upload again.
"""

from __future__ import annotations

import base64
import json

from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.domain.daf import Daf
from app.logging_setup import get_logger
from app.providers.llm import ChatMessage, chat, chat_model

# A DAF runs to about eight pages. Reading more is wasted spend, and a much
# larger upload is not a DAF.
MAX_PAGES = 12
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class DafParseError(Exception):
    pass


class ExtractedDaf(BaseModel):
    """Our schema's fields, every one optional — a scan may be unreadable."""

    full_name: str = ""
    roll_number: str = ""
    date_of_birth: str = ""
    fathers_occupation: str = ""
    home_state: str = ""
    home_district: str = ""
    graduation_subject: str = ""
    graduation_college: str = ""
    university: str = ""
    post_graduation: str = ""
    medium_of_instruction: str = ""
    optional_subject: str = ""
    hobbies: list[str] = Field(default_factory=list)
    sports_and_achievements: list[str] = Field(default_factory=list)
    positions_of_responsibility: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    service_preference: list[str] = Field(default_factory=list)
    cadre_preference: list[str] = Field(default_factory=list)
    languages_known: list[str] = Field(default_factory=list)
    attempt_number: int = 1


def page_images(pdf: bytes) -> list[tuple[str, bytes]]:
    """Full-page images from the PDF, as (mime, bytes).

    Scanned forms carry one image per page, so this needs no external tooling —
    no poppler, no Tesseract.
    """
    reader = PdfReader_from_bytes(pdf)
    out: list[tuple[str, bytes]] = []

    for page in list(reader.pages)[:MAX_PAGES]:
        for image in page.images:
            mime = "image/png" if image.name.lower().endswith(".png") else "image/jpeg"
            out.append((mime, image.data))
            break  # the page scan itself, not every embedded logo

    return out


def extract_text(pdf: bytes) -> str:
    """Selectable text, for DAFs that were generated rather than scanned."""
    reader = PdfReader_from_bytes(pdf)
    parts = []
    for page in list(reader.pages)[:MAX_PAGES]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def PdfReader_from_bytes(pdf: bytes) -> PdfReader:
    import io

    try:
        return PdfReader(io.BytesIO(pdf))
    except Exception as exc:
        raise DafParseError(f"That file could not be opened as a PDF: {exc}") from exc


_READ_PROMPT = """This is a UPSC Detailed Application Form (DAF), scanned.

Read every field you can see. Use the form's own labels, verbatim, including
their numbering. Where a field is blank, give an empty string. Do not guess or
infer anything that is not printed on the page.

Return JSON only: {"fields": {label: value}}"""


_MAP_PROMPT = """Map these DAF fields onto the target schema.

Rules:
- Copy values across; never invent one. Leave a field empty if the form does
  not carry it.
- "hobbies", "service_preference" and similar are lists — split on commas or
  numbering.
- "service_preference" and "cadre_preference" must stay in the aspirant's own
  order of preference.
- "attempt_number" is an integer; use 1 if the form does not say.
- Prefer the PERMANENT address for home_state and home_district, not the
  correspondence address.

Reply with JSON and nothing else — no preamble, no explanation, no code fence.
Match exactly this shape:
{schema}"""


async def read_pdf(log, pdf: bytes) -> tuple[dict, ExtractedDaf]:
    """Read a scanned DAF. Returns (raw fields as printed, mapped to our schema)."""
    if len(pdf) > MAX_UPLOAD_BYTES:
        raise DafParseError("That file is too large. A DAF is usually under 25 MB.")

    # Two kinds of DAF arrive. A scan is one image per page and has to be read
    # with vision. A digitally generated form has selectable text and no images
    # at all — cheaper and far more accurate to read directly.
    images = page_images(pdf)
    text = extract_text(pdf)

    if images:
        log.info(f"scanned DAF — reading {len(images)} page image(s)", pages=len(images))
        content: list[dict] = [{"type": "text", "text": _READ_PROMPT}]
        for mime, data in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"},
                }
            )
        from app.providers.llm import _call_vision

        raw_text = await _call_vision(content, max_tokens=12000)

    elif len(text.strip()) > 200:
        log.info(f"text DAF — reading {len(text)} extracted character(s)", chars=len(text))
        result = await chat(
            log,
            "cold",
            [ChatMessage("system", _READ_PROMPT), ChatMessage("user", text[:120_000])],
            max_tokens=12000,
            temperature=0.1,
        )
        raw_text = result.text

    else:
        raise DafParseError(
            "Nothing could be read from that PDF — it has neither page images nor "
            "selectable text. If it is a photograph of a form, try exporting it as "
            "a PDF scan instead."
        )
    try:
        raw_fields = json.loads(_strip_fences(raw_text)).get("fields", {})
    except json.JSONDecodeError as exc:
        raise DafParseError(
            "The form was read but the result came back incomplete. This usually "
            f"means the scan is very long or very dense. ({exc})"
        ) from exc

    if not raw_fields:
        raise DafParseError("Nothing readable was found in that PDF.")

    log.info(f"read {len(raw_fields)} field(s) from the form", fields=len(raw_fields))

    # chat_model validates against the schema and re-prompts with the specific
    # errors when the model replies with prose instead of JSON — which is what
    # it does here if simply asked nicely.
    schema = json.dumps(ExtractedDaf().model_dump(), indent=2)
    try:
        extracted, _ = await chat_model(
            log,
            "cold",
            [
                ChatMessage("system", _MAP_PROMPT.format(schema=schema)),
                ChatMessage("user", json.dumps(raw_fields, indent=2)),
            ],
            ExtractedDaf,
            max_tokens=3000,
            temperature=0.1,
        )
    except Exception as exc:
        log.error("mapping failed", error=str(exc))
        raise DafParseError(f"The form was read but could not be mapped: {exc}") from exc

    return raw_fields, extracted


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.removeprefix("json").strip()


def to_daf(extracted: ExtractedDaf) -> tuple[Daf | None, list[str]]:
    """Build a validated Daf, or report exactly what the scan did not give us.

    OCR is never trusted silently: whatever is missing comes back as a list the
    aspirant is asked to fill in before the board is convened.
    """
    payload = {
        "full_name": extracted.full_name,
        "roll_number": extracted.roll_number,
        "date_of_birth": extracted.date_of_birth,
        "fathers_occupation": extracted.fathers_occupation,
        "home_state": extracted.home_state,
        "home_district": extracted.home_district,
        "education": {
            "graduation_subject": extracted.graduation_subject,
            "graduation_college": extracted.graduation_college,
            "university": extracted.university,
            "post_graduation": extracted.post_graduation,
            "medium_of_instruction": extracted.medium_of_instruction or "English",
        },
        "optional_subject": extracted.optional_subject,
        "hobbies": extracted.hobbies,
        "sports_and_achievements": extracted.sports_and_achievements,
        "positions_of_responsibility": extracted.positions_of_responsibility,
        "work_experience": extracted.work_experience,
        "service_preference": extracted.service_preference,
        "cadre_preference": extracted.cadre_preference,
        "languages_known": extracted.languages_known,
        "attempt_number": extracted.attempt_number or 1,
    }

    try:
        return Daf.model_validate(payload), []
    except Exception:
        missing = [
            label
            for value, label in (
                (extracted.full_name, "Full name"),
                (extracted.home_state, "Home state"),
                (extracted.home_district, "Home district"),
                (extracted.graduation_subject, "Graduation subject"),
                (extracted.graduation_college, "College or university"),
                (extracted.optional_subject, "Optional subject"),
                (extracted.hobbies, "Hobbies"),
                (extracted.service_preference, "Service preference"),
            )
            if not value
        ]
        return None, missing
