"""Application configuration for the Tsumiki backend.

Loads environment from ``backend/.env.local`` via pydantic-settings (which uses
python-dotenv under the hood). Secret values are wrapped in ``SecretStr`` so they
never leak into logs, reprs, or tracebacks.

NEVER print or return secret values. Use :meth:`Settings.public_summary` for any
externally visible config.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Resolve .env.local relative to this file so config works regardless of cwd.
ENV_FILE = Path(__file__).resolve().parent / ".env.local"
load_dotenv(ENV_FILE)

# Required keys (validated on load). Listed for documentation/error messages.
REQUIRED_KEYS = (
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "OLLAMA_API_KEY",
    "OLLAMA_MODEL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "VAPI_API_KEY",
    "VAPI_ASSISTANT_ID",
)


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unrelated keys (e.g. NEXT_PUBLIC_* frontend vars)
    )

    # --- LangSmith (observability) ---
    LANGSMITH_API_KEY: SecretStr
    LANGSMITH_PROJECT: str

    # --- Ollama (LLM provider) ---
    OLLAMA_API_KEY: SecretStr
    OLLAMA_MODEL: str

    # --- Supabase (relational store) ---
    # The shared .env.local follows the Next.js convention and names the URL
    # NEXT_PUBLIC_SUPABASE_URL; accept either spelling so one file serves both
    # frontend and backend.
    SUPABASE_URL: str = Field(
        validation_alias=AliasChoices("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL"),
    )
    SUPABASE_SERVICE_ROLE_KEY: SecretStr

    # --- Vapi (voice escalation) ---
    VAPI_API_KEY: SecretStr
    VAPI_ASSISTANT_ID: str
    # The Vapi-owned caller-ID used as the FROM number on outbound calls.
    # Optional so the service boots without it; place_escalation_call raises a
    # clear error if a call is attempted while it is unset.
    VAPI_PHONE_NUMBER_ID: str | None = None

    # --- Demo helpers (optional; used only by scripts, never required to boot) ---
    DEMO_USER_ID: str | None = None
    DEMO_PHONE_NUMBER: str | None = None

    # --- Chroma (vector store) — local persistent path, not a secret ---
    CHROMA_PATH: str = str(Path(__file__).resolve().parent / ".chroma")

    @property
    def supabase_host(self) -> str:
        """Host portion of SUPABASE_URL — safe to expose (carries no credentials)."""
        return urlparse(self.SUPABASE_URL).hostname or ""

    def public_summary(self) -> dict[str, str]:
        """Non-secret config snapshot suitable for /health. Never includes secrets."""
        return {
            "ollama_model": self.OLLAMA_MODEL,
            "langsmith_project": self.LANGSMITH_PROJECT,
            "supabase_host": self.supabase_host,
        }


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, raising a clear, named error on missing keys."""
    try:
        return Settings()  # type: ignore[call-arg]  # values come from env/.env.local
    except ValidationError as exc:
        missing = [
            ".".join(str(p) for p in err["loc"])
            for err in exc.errors()
            if err.get("type") == "missing"
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s) in .env.local: "
                + ", ".join(missing)
                + ". Required keys: "
                + ", ".join(REQUIRED_KEYS)
            ) from exc
        raise
