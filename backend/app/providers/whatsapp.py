"""Updates on WhatsApp, over Meta's Cloud API.

Two halves, and it matters that they are separate:

  * The opt-in is ours. It is stored against the account, gated on a verified
    number, and revocable. That half works with no vendor at all.
  * The send is Meta's. It needs ``WHATSAPP_TOKEN`` and ``WHATSAPP_PHONE_ID``.

When those are unset this module says so and sends nothing. It does not
pretend, and neither does anything above it — a button that reports success
while no message left the building is worse than no button.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.logging_setup import get_logger

GRAPH = "https://graph.facebook.com/v21.0"
TIMEOUT_S = 10.0


def is_configured() -> bool:
    s = get_settings()
    return bool(s.whatsapp_token and s.whatsapp_phone_id)


def business_number() -> str:
    """The number an aspirant messages to open the thread from their side."""
    return get_settings().whatsapp_business_number


def opt_in_link(text: str = "Start my PanelMind updates") -> str | None:
    """A wa.me deep link that genuinely opens WhatsApp with the message ready.

    This is the real opt-in path: on WhatsApp a business may only message
    someone who messaged it first, so the aspirant has to send that first line.
    Returns None when no business number is configured, and the UI then does
    not offer a link that would go nowhere.
    """
    number = business_number().lstrip("+").replace(" ", "")
    if not number:
        return None
    from urllib.parse import quote

    return f"https://wa.me/{number}?text={quote(text)}"


async def send_text(to_number: str, body: str) -> dict:
    """Send one message. Returns what happened, truthfully.

    ``{"sent": False, "reason": ...}`` when there is no channel configured or
    the Graph API refused — never a bare success.
    """
    log = get_logger(component="whatsapp")

    if not is_configured():
        log.info("whatsapp send skipped — no channel configured")
        return {
            "sent": False,
            "reason": "WhatsApp sending is not configured on this deployment.",
            "configured": False,
        }

    settings = get_settings()
    to = to_number.lstrip("+").replace(" ", "")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            response = await client.post(
                f"{GRAPH}/{settings.whatsapp_phone_id}/messages",
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": body},
                },
            )
    except Exception as exc:
        log.warning("whatsapp send failed", error=str(exc))
        return {"sent": False, "reason": str(exc)[:200], "configured": True}

    if response.status_code >= 400:
        detail = response.text[:300]
        log.warning("whatsapp rejected the send", status=response.status_code, detail=detail)
        return {"sent": False, "reason": detail, "configured": True}

    message_id = (response.json().get("messages") or [{}])[0].get("id", "")
    log.info("whatsapp message sent", to=to, message_id=message_id)
    return {"sent": True, "message_id": message_id, "configured": True}
