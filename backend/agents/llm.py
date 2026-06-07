"""Shared LLM-client construction for the agent nodes.

Every agent talks to the same Ollama Cloud endpoint via ``ChatOllama`` (from
``langchain-ollama``), authenticated with ``OLLAMA_API_KEY`` and defaulting to
``OLLAMA_MODEL`` from config. Each agent constructor accepts an optional ``model``
override so a different model can be pinned per node — this satisfies the
"models swappable per agent" tech-stack decision (the capability must exist; we do
not actually run different models in the demo).

Construction is lazy: agents build their client on first use, so unit tests can
inject a fake LLM and never touch config, the network, or a real key.
"""

from __future__ import annotations

from typing import Any

# Ollama Cloud's OpenAI/Ollama-compatible endpoint. The local default
# (http://localhost:11434) would never reach the hosted models, so it is set
# explicitly here and authenticated with a bearer token.
OLLAMA_CLOUD_BASE_URL = "https://ollama.com"


def build_chat_model(model: str | None = None) -> Any:
    """Return a ``ChatOllama`` pointed at Ollama Cloud.

    ``model`` overrides ``config.OLLAMA_MODEL`` for this one client. Imports are
    lazy so importing an agent module costs nothing and needs no settings.
    """
    from langchain_ollama import ChatOllama  # lazy

    from config import get_settings  # lazy

    settings = get_settings()
    return ChatOllama(
        model=model or settings.OLLAMA_MODEL,
        base_url=OLLAMA_CLOUD_BASE_URL,
        client_kwargs={
            "headers": {
                "Authorization": f"Bearer {settings.OLLAMA_API_KEY.get_secret_value()}"
            }
        },
        temperature=0,  # keep generations as stable as a sampling model allows
    )
