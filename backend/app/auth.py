"""Accounts and sign-in.

Phone number is the identity. A returning aspirant enters their number and a
six-digit code; a new one is additionally asked for a name and email once, and
never again.

The OTP sender is deliberately behind an interface. In development the code is
logged and returned so the flow is testable end to end; wiring a real gateway
(MSG91, Twilio) is a single class, and nothing above this module changes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import get_settings
from app.logging_setup import get_logger, new_id

OTP_TTL_S = 5 * 60
OTP_LENGTH = 6
MAX_ATTEMPTS = 5
# Throttle: a number may not be sent more than this many codes per window.
SEND_WINDOW_S = 15 * 60
MAX_SENDS_PER_WINDOW = 5
SESSION_TTL_S = 30 * 24 * 3600

_E164 = re.compile(r"^\+?[1-9]\d{7,14}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")

Channel = Literal["phone", "email"]


def normalise_email(raw: str) -> str:
    cleaned = raw.strip().lower()
    if not _EMAIL.match(cleaned):
        raise ValueError("That does not look like a valid email address.")
    return cleaned


def normalise_identifier(raw: str) -> tuple[Channel, str]:
    """Work out whether the aspirant typed a phone number or an email.

    Sign-in accepts either; the code goes to whichever they gave. There is no
    password anywhere in the system.
    """
    candidate = raw.strip()
    if "@" in candidate:
        return "email", normalise_email(candidate)
    return "phone", normalise_phone(candidate)


def normalise_phone(raw: str) -> str:
    """Reduce a typed number to E.164. Assumes India when no country code."""
    digits = re.sub(r"[^\d+]", "", raw.strip())

    if digits.startswith("+"):
        candidate = digits
    elif len(digits) == 10:
        candidate = f"+91{digits}"
    elif digits.startswith("91") and len(digits) == 12:
        candidate = f"+{digits}"
    elif digits.startswith("0") and len(digits) == 11:
        candidate = f"+91{digits[1:]}"
    else:
        candidate = f"+{digits}"

    if not _E164.match(candidate):
        raise ValueError("That does not look like a valid phone number.")
    return candidate


class OtpSender(Protocol):
    async def send(self, channel: Channel, destination: str, code: str) -> None: ...


class ConsoleOtpSender:
    """Development sender.

    Logs the code instead of dispatching an SMS or email. ``reveals_code`` is
    what the API checks before echoing the code back to the client — a
    production sender must never set it.
    """

    reveals_code = True

    def __init__(self) -> None:
        self._log = get_logger(component="auth.otp")

    async def send(self, channel: Channel, destination: str, code: str) -> None:
        self._log.info(
            f"OTP for {destination}: {code}",
            destination=destination,
            code=code,
            channel=channel,
            transport="console",
        )


@dataclass(slots=True)
class User:
    id: str
    phone: str
    name: str
    email: str
    created_at: float = field(default_factory=time.time)
    # Denormalised counters so the dashboard does not scan every session.
    mocks_taken: int = 0
    last_seen_at: float = field(default_factory=time.time)

    # A contact is verified when a code was sent to it and came back correct.
    # The channel used to sign in is therefore verified by definition; one
    # added afterwards at the profile step is not, until its own code is
    # confirmed.
    email_verified: bool = False
    phone_verified: bool = False
    # Updates on WhatsApp. Only meaningful with a verified phone.
    whatsapp_opt_in: bool = False
    has_avatar: bool = False

    @property
    def is_complete(self) -> bool:
        # Both contacts, so the aspirant can sign in with either next time.
        return bool(self.name and self.email and self.phone)

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


@dataclass(slots=True)
class PendingOtp:
    channel: Channel
    destination: str
    code_hash: str
    expires_at: float
    attempts: int = 0


class StartRequest(BaseModel):
    """Phone or email — whichever the aspirant prefers."""

    identifier: str = Field(min_length=5, max_length=120)


class VerifyRequest(BaseModel):
    identifier: str = Field(min_length=5, max_length=120)
    code: str = Field(min_length=OTP_LENGTH, max_length=OTP_LENGTH)

    @field_validator("code")
    @classmethod
    def _digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("The code is six digits.")
        return value


class CompleteProfileRequest(BaseModel):
    """Fills whatever the sign-in channel did not already supply."""

    name: str = Field(min_length=2, max_length=80)
    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Please give your full name.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        return None if value is None or not value.strip() else normalise_phone(value)


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _hash_code(destination: str, code: str) -> str:
    """Codes are never stored in the clear, even in memory.

    Binding the destination into the hash is what stops a code issued for one
    identity being redeemed against another.
    """
    secret = get_settings().livekit_api_secret.encode()
    return hmac.new(secret, f"{destination}:{code}".encode(), hashlib.sha256).hexdigest()


def _sign(payload: dict) -> str:
    """Minimal signed session token. Opaque to the client."""
    secret = get_settings().livekit_api_secret.encode()
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    raw = body.hex()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def _verify(token: str) -> dict | None:
    try:
        raw, signature = token.split(".", 1)
        body = bytes.fromhex(raw)
    except (ValueError, AttributeError):
        return None

    secret = get_settings().livekit_api_secret.encode()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    payload = json.loads(body)
    if payload.get("exp", 0) < time.time():
        return None
    return payload


# Where accounts live between restarts.
ACCOUNTS_PATH = Path(os.environ.get("BOARD_ACCOUNTS_STORE", ".accounts.json"))


class AuthStore:
    """Accounts, persisted to disk.

    Holding these in memory alone meant every API restart signed everybody out
    mid-session: a token still verified, but the user it named was gone, so
    every authenticated call returned 401. Pending one-time codes are
    deliberately NOT persisted — a restart should invalidate them.
    """

    def __init__(self, sender: OtpSender | None = None, path: Path | None = None) -> None:
        self._users_by_phone: dict[str, User] = {}
        self._users_by_email: dict[str, User] = {}
        self._users_by_id: dict[str, User] = {}
        self._pending: dict[str, PendingOtp] = {}
        self._sends: dict[str, list[float]] = {}
        self.sender = sender or ConsoleOtpSender()
        self._log = get_logger(component="auth")
        self._path = path
        if self._path is not None:
            self._load()

    # --- persistence -----------------------------------------------------

    def _load(self) -> None:
        assert self._path is not None
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
        except Exception as exc:
            self._log.warning("could not read the account store", error=str(exc))
            return

        for row in raw.get("users", []):
            try:
                user = User(**row)
            except Exception:
                continue
            self._index(user)

        if self._users_by_id:
            self._log.info(f"restored {len(self._users_by_id)} account(s)")

    def _persist(self) -> None:
        if self._path is None:
            return
        try:
            payload = {
                "users": [
                    {
                        "id": u.id,
                        "phone": u.phone,
                        "name": u.name,
                        "email": u.email,
                        "created_at": u.created_at,
                        "mocks_taken": u.mocks_taken,
                        "last_seen_at": u.last_seen_at,
                        "email_verified": u.email_verified,
                        "phone_verified": u.phone_verified,
                        "whatsapp_opt_in": u.whatsapp_opt_in,
                        "has_avatar": u.has_avatar,
                    }
                    for u in self._users_by_id.values()
                ]
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload))
            tmp.replace(self._path)  # atomic
        except Exception as exc:
            self._log.warning("could not persist accounts", error=str(exc))

    def find(self, channel: Channel, destination: str) -> User | None:
        index = self._users_by_phone if channel == "phone" else self._users_by_email
        return index.get(destination)

    def _index(self, user: User) -> None:
        self._users_by_id[user.id] = user
        if user.phone:
            self._users_by_phone[user.phone] = user
        if user.email:
            self._users_by_email[user.email] = user

    # --- sign-in ---------------------------------------------------------

    async def start_login(self, identifier: str) -> dict:
        channel, destination = normalise_identifier(identifier)
        now = time.time()

        recent = [t for t in self._sends.get(destination, []) if now - t < SEND_WINDOW_S]
        if len(recent) >= MAX_SENDS_PER_WINDOW:
            raise AuthError(
                "Too many codes requested. Try again in a few minutes.", status=429
            )
        recent.append(now)
        self._sends[destination] = recent

        code = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
        self._pending[destination] = PendingOtp(
            channel=channel,
            destination=destination,
            code_hash=_hash_code(destination, code),
            expires_at=now + OTP_TTL_S,
        )

        await self.sender.send(channel, destination, code)

        existing = self.find(channel, destination)
        self._log.info(
            "otp dispatched",
            channel=channel,
            destination=destination,
            returning=existing is not None,
        )

        payload = {
            "sent": True,
            "channel": channel,
            "destination": destination,
            "returning_user": existing is not None,
            "expires_in": OTP_TTL_S,
        }
        # Development convenience only. A real gateway never reveals the code.
        if getattr(self.sender, "reveals_code", False):
            payload["dev_code"] = code
        return payload

    async def verify(self, identifier: str, code: str) -> tuple[User, str, bool]:
        channel, destination = normalise_identifier(identifier)
        pending = self._pending.get(destination)

        if pending is None:
            raise AuthError("Request a code first.", status=400)

        if time.time() > pending.expires_at:
            del self._pending[destination]
            raise AuthError("That code has expired. Request a new one.", status=400)

        pending.attempts += 1
        if pending.attempts > MAX_ATTEMPTS:
            del self._pending[destination]
            raise AuthError("Too many wrong attempts. Request a new code.", status=429)

        if not hmac.compare_digest(pending.code_hash, _hash_code(destination, code)):
            raise AuthError("That code is not right.", status=400)

        del self._pending[destination]
        self._sends.pop(destination, None)

        user = self.find(channel, destination)
        is_new = user is None

        if user is None:
            # Created with whichever channel signed in; the profile step
            # collects the name and the contact detail still missing.
            user = User(
                id=new_id("usr"),
                phone=destination if channel == "phone" else "",
                email=destination if channel == "email" else "",
                name="",
            )
            self._index(user)

        # Signing in through a channel proves the aspirant holds it.
        if channel == "phone":
            user.phone_verified = True
        else:
            user.email_verified = True

        user.last_seen_at = time.time()
        self._persist()
        self._log.info(
            "signed in", user_id=user.id, channel=channel, is_new=is_new
        )

        return user, self.issue_token(user), is_new

    def issue_token(self, user: User) -> str:
        return _sign({"sub": user.id, "exp": time.time() + SESSION_TTL_S})

    def user_from_token(self, token: str | None) -> User | None:
        if not token:
            return None
        payload = _verify(token)
        if payload is None:
            return None
        return self._users_by_id.get(payload.get("sub", ""))

    def complete_profile(
        self,
        user: User,
        name: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> User:
        """Fill in the name plus whichever contact detail sign-in did not give.

        Normalised here rather than only in the request model, so no caller can
        write a ragged name or an unindexed contact into the account.
        """
        user.name = " ".join(name.split())

        if email:
            cleaned = normalise_email(email)
            other = self._users_by_email.get(cleaned)
            if other is not None and other.id != user.id:
                raise AuthError("That email is already on another account.", status=409)
            # Changing a contact un-verifies it. Anything else would let one
            # verified address launder an unverified one in behind it.
            if cleaned != user.email:
                self._users_by_email.pop(user.email, None)
                user.email_verified = False
            user.email = cleaned

        if phone:
            cleaned = normalise_phone(phone)
            other = self._users_by_phone.get(cleaned)
            if other is not None and other.id != user.id:
                raise AuthError("That number is already on another account.", status=409)
            if cleaned != user.phone:
                self._users_by_phone.pop(user.phone, None)
                user.phone_verified = False
                # An opt-in belongs to the number it was given for.
                user.whatsapp_opt_in = False
            user.phone = cleaned

        # Re-index so the aspirant can sign in with either detail next time.
        self._index(user)
        self._persist()
        self._log.info("profile completed", user_id=user.id)
        return user

    # --- verifying a contact after the fact -------------------------------
    #
    # The channel used to sign in is verified by definition. The other one is
    # typed in at the profile step and nobody has proved it works, so it gets
    # the same one-time code — the same machinery, aimed at an account that
    # already exists rather than at creating one.

    async def start_contact_verification(self, user: User, channel: Channel) -> dict:
        destination = user.phone if channel == "phone" else user.email
        if not destination:
            raise AuthError(f"Add a {channel} first.", status=400)
        if (user.phone_verified if channel == "phone" else user.email_verified):
            return {"sent": False, "already_verified": True, "channel": channel}

        now = time.time()
        recent = [t for t in self._sends.get(destination, []) if now - t < SEND_WINDOW_S]
        if len(recent) >= MAX_SENDS_PER_WINDOW:
            raise AuthError("Too many codes requested. Try again in a few minutes.", status=429)
        recent.append(now)
        self._sends[destination] = recent

        code = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
        self._pending[destination] = PendingOtp(
            channel=channel,
            destination=destination,
            code_hash=_hash_code(destination, code),
            expires_at=now + OTP_TTL_S,
        )
        await self.sender.send(channel, destination, code)
        self._log.info("verification code dispatched", user_id=user.id, channel=channel)

        payload = {
            "sent": True,
            "channel": channel,
            "destination": destination,
            "expires_in": OTP_TTL_S,
        }
        if getattr(self.sender, "reveals_code", False):
            payload["dev_code"] = code
        return payload

    def confirm_contact(self, user: User, channel: Channel, code: str) -> User:
        destination = user.phone if channel == "phone" else user.email
        pending = self._pending.get(destination)

        if pending is None:
            raise AuthError("Request a code first.", status=400)
        if time.time() > pending.expires_at:
            del self._pending[destination]
            raise AuthError("That code has expired. Request a new one.", status=400)

        pending.attempts += 1
        if pending.attempts > MAX_ATTEMPTS:
            del self._pending[destination]
            raise AuthError("Too many wrong attempts. Request a new code.", status=429)

        if not hmac.compare_digest(pending.code_hash, _hash_code(destination, code)):
            raise AuthError("That code is not right.", status=400)

        del self._pending[destination]
        self._sends.pop(destination, None)

        if channel == "phone":
            user.phone_verified = True
        else:
            user.email_verified = True

        self._persist()
        self._log.info("contact verified", user_id=user.id, channel=channel)
        return user

    def set_whatsapp(self, user: User, opt_in: bool) -> User:
        """Turn updates on WhatsApp on or off.

        Gated on a verified number: sending to a number nobody has proved they
        hold is how a product ends up messaging strangers.
        """
        if opt_in and not user.phone_verified:
            raise AuthError("Verify your mobile number first.", status=400)
        user.whatsapp_opt_in = opt_in
        self._persist()
        self._log.info("whatsapp preference set", user_id=user.id, opt_in=opt_in)
        return user

    def set_avatar_flag(self, user: User, present: bool) -> None:
        user.has_avatar = present
        self._persist()

    async def ensure_persisted(self, user: User) -> None:
        """Force this account to durable storage, now.

        The Postgres store writes accounts behind the request so sign-in never
        waits on the database. Anything that then inserts a row referencing
        ``users(id)`` has to close that gap first, or the foreign key can find
        nothing there — which under load it did.
        """
        self._persist()

    def get(self, user_id: str) -> User | None:
        return self._users_by_id.get(user_id)

    def record_mock(self, user_id: str) -> None:
        user = self._users_by_id.get(user_id)
        if user is not None:
            user.mocks_taken += 1
            self._persist()


store = AuthStore(path=ACCOUNTS_PATH)


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "name": user.name,
        "email": user.email,
        "initials": user.initials,
        "is_complete": user.is_complete,
        "mocks_taken": user.mocks_taken,
        "created_at": user.created_at,
        "email_verified": user.email_verified,
        "phone_verified": user.phone_verified,
        "whatsapp_opt_in": user.whatsapp_opt_in,
        "has_avatar": user.has_avatar,
    }
