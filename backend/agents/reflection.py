"""Reflection Agent (agents.md §3).

The long-term memory / pattern-recognition layer. Runs **periodically** (its own
entry point), NOT on the per-check-in path. It reads ``checkin_history``, queries
the vector store for semantically similar past notes, asks the LLM for 1-3 concise
structured insights, then writes those insights to BOTH ``reflection_notes`` (so
the next Planner cycle routes around them) and the vector store (so future runs can
retrieve them semantically).

This is the agent that makes Tsumiki "remember you" instead of starting fresh —
the direct answer to the "ChatGPT forgets everything" complaint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agents.llm import build_chat_model
from state import CheckIn, UserState


class _Insights(BaseModel):
    insights: list[str] = Field(
        description=(
            "1-3 concise, structured insight strings, e.g. '~80% of missed sessions "
            "fall on Mondays — likely a recurring scheduling conflict'."
        ),
        min_length=0,
        max_length=3,
    )


_SYSTEM = (
    "You are Tsumiki's Reflection analyst. You look at a user's check-in history "
    "and past notes and surface 1-3 concise, actionable patterns (timing, "
    "frequency, recurring friction). Phrase each as a short factual insight the "
    "Planner can route around. Do not moralize; gaps are information, not failures."
)


def _summarize_history(history: list[CheckIn]) -> str:
    """Compact the check-in log into a small prompt-friendly summary.

    We never dump the whole history into the prompt (per the tech notes); we pass a
    narrow, structured digest: per-weekday completed/missed counts.
    """
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    tally: dict[str, list[int]] = {d: [0, 0] for d in weekdays}  # [completed, missed]
    for ci in history:
        ts = ci.get("timestamp")
        if not isinstance(ts, datetime):
            continue
        bucket = tally[weekdays[ts.weekday()]]
        bucket[0 if ci.get("completed") else 1] += 1
    parts = [
        f"{d}: {c} done / {m} missed" for d, (c, m) in tally.items() if c or m
    ]
    return "; ".join(parts) or "no check-ins recorded yet"


class ReflectionAgent:
    """LangGraph node (separate periodic graph): writes ``reflection_notes``."""

    def __init__(
        self,
        model: str | None = None,
        llm: Any | None = None,
        vector: Any | None = None,
    ) -> None:
        self._model = model
        self._llm = llm
        self._vector = vector

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = build_chat_model(self._model)
        return self._llm

    @property
    def vector(self) -> Any:
        if self._vector is None:
            from memory.vector import VectorMemory  # lazy

            self._vector = VectorMemory()
        return self._vector

    def __call__(self, state: UserState) -> dict:
        user_id = state["user_id"]
        history = state.get("checkin_history") or []
        digest = _summarize_history(history)

        # Pull semantically similar past notes to ground the analysis.
        similar = self.vector.query_similar(user_id, digest, k=5)

        human = (
            f"Check-in digest by weekday: {digest}.\n"
            f"Similar past notes: {similar or 'none'}.\n\n"
            "Surface 1-3 concise insights."
        )
        structured = self.llm.with_structured_output(_Insights)
        result: _Insights = structured.invoke(
            [("system", _SYSTEM), ("human", human)]
        )

        new_notes = [n for n in result.insights if n.strip()]

        # Persist for future semantic retrieval, tagged by goal domain.
        goal = state.get("active_goal") or {}
        for note in new_notes:
            self.vector.add_reflection(
                user_id, note, {"source": "reflection", "domain": goal.get("domain", "")}
            )

        return {"reflection_notes": [*(state.get("reflection_notes") or []), *new_notes]}
