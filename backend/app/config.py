"""Typed, validated configuration.

Fails loudly at startup rather than at 3am mid-interview. Every value the
system needs is declared here; nothing reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TtsProviderName = Literal["elevenlabs", "deepgram"]

VALID_TTS_PROVIDERS: tuple[str, ...] = ("elevenlabs", "deepgram")

# The .env lives at the repo root, one level above backend/.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM: hot path (must be fast) ---
    groq_api_key: str = Field(min_length=1)
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    groq_summary_model: str = "llama-3.1-8b-instant"

    # --- LLM: cold path (must be smart) ---
    openrouter_api_key: str = Field(min_length=1)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4.6"
    openrouter_max_retries: int = Field(default=3, ge=0, le=10)

    # --- Speech ---
    deepgram_api_key: str = Field(min_length=1)
    elevenlabs_api_key: str = Field(min_length=1)
    elevenlabs_style: float = Field(default=0.45, ge=0.0, le=1.0)
    elevenlabs_stability: float = Field(default=0.55, ge=0.0, le=1.0)

    # --- Realtime transport ---
    livekit_url: str
    livekit_api_key: str = Field(min_length=1)
    livekit_api_secret: str = Field(min_length=1)

    # --- Database ---
    # Local Postgres. Unset falls back to the on-disk JSON stores, which keeps
    # tests and a fresh checkout working without a server.
    database_url: str = ""

    # --- WhatsApp updates (Meta Cloud API) ---
    # Unset means the product can still record an aspirant's opt-in and open
    # the chat for them, but cannot send outbound messages. Every surface that
    # depends on this says so rather than pretending a message went out.
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    # The business number an aspirant messages to start the thread.
    whatsapp_business_number: str = ""

    # --- Embeddings (DAF retrieval) ---
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-3-lite"

    # --- Runtime ---
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["trace", "debug", "info", "warn", "error"] = "info"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Ordered TTS preference. First provider that is healthy wins.
    tts_provider_chain: str = "elevenlabs,deepgram"

    @field_validator("livekit_url")
    @classmethod
    def _livekit_must_be_wss(cls, value: str) -> str:
        if not value.startswith("wss://"):
            raise ValueError("LIVEKIT_URL must be a wss:// URL")
        return value

    @field_validator("tts_provider_chain")
    @classmethod
    def _chain_must_resolve(cls, value: str) -> str:
        names = [p.strip().lower() for p in value.split(",") if p.strip()]
        valid = [n for n in names if n in VALID_TTS_PROVIDERS]
        if not valid:
            raise ValueError(
                f"TTS_PROVIDER_CHAIN resolved to no valid providers. "
                f"Valid names: {', '.join(VALID_TTS_PROVIDERS)}"
            )
        return ",".join(valid)

    # --- Derived accessors ---

    @property
    def is_prod(self) -> bool:
        return self.environment == "production"

    @property
    def tts_chain(self) -> list[TtsProviderName]:
        return [p for p in self.tts_provider_chain.split(",")]  # type: ignore[misc]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def livekit_http_url(self) -> str:
        return self.livekit_url.replace("wss://", "https://")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache settings. Raises pydantic ValidationError if misconfigured."""
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    """Test-only: force a re-read of the environment."""
    get_settings.cache_clear()
