"""Vector memory backend (Chroma).

Stores free-text reflections and qualitative notes for semantic retrieval
(e.g. "user struggles with mornings"). Uses a local *persistent* Chroma client —
no hosted vector DB is needed for the hackathon.

NOTE ON EMBEDDINGS: this uses Chroma's DEFAULT embedding function
(all-MiniLM-L6-v2 via onnxruntime), NOT Ollama. Reflections are embedded locally
by Chroma; the Ollama model configured for the agents is intentionally not
involved in vectorization. Swap in a custom embedding function later if desired.

The collection (or client) is injectable so tests can pass a fake; the real
``chromadb`` dependency is imported lazily only when nothing is supplied.
"""

from __future__ import annotations

import uuid
from typing import Any

_COLLECTION_NAME = "reflections"


class VectorMemory:
    """Semantic store for qualitative reflection notes, scoped per user."""

    def __init__(self, collection: Any | None = None, client: Any | None = None) -> None:
        if collection is None:
            if client is None:
                import chromadb  # lazy

                from config import get_settings  # lazy

                client = chromadb.PersistentClient(path=get_settings().CHROMA_PATH)
            # Default embedding function (local MiniLM) — NOT Ollama. See module note.
            collection = client.get_or_create_collection(_COLLECTION_NAME)
        self.collection = collection

    def add_reflection(self, user_id: str, text: str, metadata: dict) -> None:
        """Embed and store one reflection, tagged with ``user_id`` for scoping."""
        meta = {**(metadata or {}), "user_id": user_id}
        self.collection.add(
            documents=[text],
            metadatas=[meta],
            ids=[str(uuid.uuid4())],
        )

    def query_similar(self, user_id: str, query_text: str, k: int = 5) -> list[str]:
        """Return up to ``k`` semantically similar reflection texts for the user."""
        result = self.collection.query(
            query_texts=[query_text],
            n_results=k,
            where={"user_id": user_id},
        )
        documents = (result or {}).get("documents") or []
        if not documents:
            return []
        return list(documents[0])
