"""Sign-in.

Phone numbers arrive in every shape an Indian aspirant might type them, so
normalisation is pinned exactly. The rest guards the things that would let
someone into another person's account.
"""

from __future__ import annotations

import time

import pytest

from app.auth import (
    MAX_ATTEMPTS,
    MAX_SENDS_PER_WINDOW,
    AuthError,
    AuthStore,
    ConsoleOtpSender,
    normalise_identifier,
    normalise_phone,
)

PHONE = "+919701337681"


class RecordingSender(ConsoleOtpSender):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, channel: str, destination: str, code: str) -> None:
        self.sent.append((channel, destination, code))


@pytest.fixture
def store() -> AuthStore:
    return AuthStore(sender=RecordingSender())


async def sign_in(store: AuthStore, identifier: str = PHONE):
    await store.start_login(identifier)
    code = store.sender.sent[-1][2]  # type: ignore[attr-defined]
    return await store.verify(identifier, code)


class TestPhoneNormalisation:
    @pytest.mark.parametrize(
        "typed",
        ["9701337681", "+919701337681", "919701337681", "09701337681",
         "97013 37681", "+91 97013-37681"],
    )
    def test_indian_numbers_reduce_to_one_identity(self, typed):
        assert normalise_phone(typed) == PHONE

    def test_keeps_an_explicit_country_code(self):
        assert normalise_phone("+14155552671") == "+14155552671"

    @pytest.mark.parametrize("bad", ["12345", "abcdefghij", "", "+0123456789"])
    def test_rejects_what_is_not_a_phone_number(self, bad):
        with pytest.raises(ValueError):
            normalise_phone(bad)


class TestSignIn:
    async def test_a_new_number_creates_an_account_needing_a_profile(self, store):
        user, token, is_new = await sign_in(store)

        assert is_new is True
        assert user.phone == PHONE
        assert user.is_complete is False, "name and email are still required"
        assert token

    async def test_a_returning_number_signs_straight_in(self, store):
        user, _, _ = await sign_in(store)
        store.complete_profile(user, "Rohit Sharma", email="rohit@example.com")

        again, _, is_new = await sign_in(store)

        assert is_new is False
        assert again.id == user.id, "a returning number must not create a second account"
        assert again.is_complete is True

    async def test_the_code_is_never_held_in_the_clear(self, store):
        await store.start_login(PHONE)
        code = store.sender.sent[-1][2]
        pending = store._pending[PHONE]

        assert code not in pending.code_hash
        assert len(pending.code_hash) == 64

    async def test_a_wrong_code_is_refused(self, store):
        await store.start_login(PHONE)
        with pytest.raises(AuthError, match="not right"):
            await store.verify(PHONE, "000000")

    async def test_a_code_from_one_number_cannot_sign_in_another(self, store):
        await store.start_login(PHONE)
        code = store.sender.sent[-1][2]

        other = "+919000000001"
        await store.start_login(other)

        with pytest.raises(AuthError):
            await store.verify(other, code)

    async def test_a_code_works_once(self, store):
        await store.start_login(PHONE)
        code = store.sender.sent[-1][2]
        await store.verify(PHONE, code)

        with pytest.raises(AuthError, match="Request a code first"):
            await store.verify(PHONE, code)

    async def test_an_expired_code_is_refused(self, store):
        await store.start_login(PHONE)
        code = store.sender.sent[-1][2]
        store._pending[PHONE].expires_at = time.time() - 1

        with pytest.raises(AuthError, match="expired"):
            await store.verify(PHONE, code)

    async def test_guessing_is_locked_out(self, store):
        await store.start_login(PHONE)

        for _ in range(MAX_ATTEMPTS):
            with pytest.raises(AuthError):
                await store.verify(PHONE, "000000")

        with pytest.raises(AuthError, match="Too many wrong attempts"):
            await store.verify(PHONE, "000000")

    async def test_code_requests_are_throttled(self, store):
        for _ in range(MAX_SENDS_PER_WINDOW):
            await store.start_login(PHONE)

        with pytest.raises(AuthError, match="Too many codes"):
            await store.start_login(PHONE)


class TestSessions:
    async def test_a_token_resolves_to_its_owner(self, store):
        user, token, _ = await sign_in(store)
        assert store.user_from_token(token).id == user.id

    @pytest.mark.parametrize("bad", ["", "rubbish", "aa.bb", None])
    async def test_a_forged_token_resolves_to_nobody(self, store, bad):
        await sign_in(store)
        assert store.user_from_token(bad) is None

    async def test_a_tampered_payload_is_rejected(self, store):
        _, token, _ = await sign_in(store)
        body, signature = token.split(".", 1)
        # Flip one byte of the payload, keep the original signature.
        forged = f"{body[:-2]}00.{signature}"
        assert store.user_from_token(forged) is None

    async def test_an_expired_session_is_rejected(self, store, monkeypatch):
        import app.auth as auth

        monkeypatch.setattr(auth, "SESSION_TTL_S", -1)
        _, token, _ = await sign_in(store)
        assert store.user_from_token(token) is None


class TestProfile:
    async def test_completing_the_profile_finishes_the_account(self, store):
        user, _, _ = await sign_in(store)
        store.complete_profile(user, "  Rohit   Sharma ", email="rohit@example.com")

        assert user.name == "Rohit Sharma"
        assert user.is_complete is True
        assert user.initials == "RS"

    async def test_initials_survive_a_single_name(self, store):
        user, _, _ = await sign_in(store)
        store.complete_profile(user, "Rohit", email="rohit@example.com")
        assert user.initials == "R"


EMAIL = "rohit@example.com"


class TestIdentifierRouting:
    @pytest.mark.parametrize(
        "typed,expected",
        [
            ("9701337681", ("phone", PHONE)),
            ("+91 97013-37681", ("phone", PHONE)),
            ("Rohit@Example.COM ", ("email", EMAIL)),
            (" rohit@example.com", ("email", EMAIL)),
        ],
    )
    def test_routes_to_the_right_channel(self, typed, expected):
        assert normalise_identifier(typed) == expected

    @pytest.mark.parametrize("bad", ["rohit@", "@example.com", "rohit@example", "nope"])
    def test_rejects_a_malformed_identifier(self, bad):
        with pytest.raises(ValueError):
            normalise_identifier(bad)


class TestEmailSignIn:
    async def test_an_email_can_create_an_account(self, store):
        user, token, is_new = await sign_in(store, EMAIL)

        assert is_new is True
        assert user.email == EMAIL
        assert user.phone == "", "phone is collected in the profile step"
        assert user.is_complete is False
        assert token

    async def test_the_code_goes_to_the_email_channel(self, store):
        await store.start_login(EMAIL)
        channel, destination, _ = store.sender.sent[-1]

        assert channel == "email"
        assert destination == EMAIL

    async def test_signing_up_by_email_then_in_by_phone_is_one_account(self, store):
        user, _, _ = await sign_in(store, EMAIL)
        store.complete_profile(user, "Rohit Sharma", phone=PHONE)
        assert user.is_complete is True

        # The phone was indexed by the profile step, so it now signs in.
        again, _, is_new = await sign_in(store, PHONE)

        assert is_new is False
        assert again.id == user.id, "one person must not end up with two accounts"

    async def test_signing_up_by_phone_then_in_by_email_is_one_account(self, store):
        user, _, _ = await sign_in(store, PHONE)
        store.complete_profile(user, "Rohit Sharma", email=EMAIL)

        again, _, is_new = await sign_in(store, EMAIL)

        assert is_new is False
        assert again.id == user.id

    async def test_a_code_for_an_email_cannot_redeem_a_phone(self, store):
        await store.start_login(EMAIL)
        code = store.sender.sent[-1][2]
        await store.start_login(PHONE)

        with pytest.raises(AuthError):
            await store.verify(PHONE, code)

    async def test_an_email_already_on_another_account_is_refused(self, store):
        first, _, _ = await sign_in(store, EMAIL)
        store.complete_profile(first, "Rohit Sharma", phone=PHONE)

        second, _, _ = await sign_in(store, "+919000000002")
        with pytest.raises(AuthError, match="already on another account"):
            store.complete_profile(second, "Someone Else", email=EMAIL)

    async def test_an_account_is_incomplete_until_both_contacts_are_known(self, store):
        user, _, _ = await sign_in(store, EMAIL)
        store.complete_profile(user, "Rohit Sharma")
        assert user.is_complete is False, "phone still missing"

        store.complete_profile(user, "Rohit Sharma", phone=PHONE)
        assert user.is_complete is True
