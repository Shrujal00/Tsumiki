"""Game Master Agent (agents.md §4).

**No LLM call.** This node exists purely to keep a clean boundary between "agents
that exercise judgment" (planning, tone, escalation) and "code that guarantees
deterministic, demoable outcomes" (the visual). It reads the ``pending_event`` set
upstream, validates it against the ``AgentEvent`` schema, attaches/refines a
``difficulty`` tag with simple deterministic rules (milestone size → difficulty),
and passes the enriched event onward to the Tsumiki Engine.

Per the spec, this is deliberately *not* folded into the Accountability Agent —
the separation is the point.
"""

from __future__ import annotations

from datetime import datetime
from typing import get_args

from state import AgentEvent, Difficulty, EventType, UserState

_EVENT_TYPES = set(get_args(EventType))
_DIFFICULTIES = set(get_args(Difficulty))


class GameMasterAgent:
    """LangGraph node: validates + enriches ``pending_event``. Deterministic."""

    def __call__(self, state: UserState) -> dict:
        event = state.get("pending_event")
        if event is None:
            return {}

        validated = self._validate(event)
        enriched: AgentEvent = {
            **validated,
            "difficulty": self._difficulty_for(validated, state),
        }
        return {"pending_event": enriched}

    # ----- deterministic validation ------------------------------------ #
    @staticmethod
    def _validate(event: AgentEvent) -> AgentEvent:
        etype = event.get("type")
        if etype not in _EVENT_TYPES:
            raise ValueError(f"Unknown AgentEvent type: {etype!r}")
        if not event.get("goal_id") and event.get("goal_id") != "":
            raise ValueError("AgentEvent.goal_id is required")
        if not isinstance(event.get("timestamp"), datetime):
            raise ValueError("AgentEvent.timestamp must be a datetime")
        return event

    # ----- deterministic difficulty rule (milestone size → difficulty) -- #
    @staticmethod
    def _difficulty_for(event: AgentEvent, state: UserState) -> Difficulty:
        """Pick a stone difficulty from simple, fixed rules.

        A maintained streak is always a ``small`` reinforcement. Otherwise the
        achievement's weight scales with how large the goal is (its milestone
        count), so finishing a step of an ambitious goal earns a bigger stone.
        """
        if event["type"] == "streak_maintained":
            return "small"

        goal = state.get("active_goal") or {}
        milestone_count = len(goal.get("milestones") or [])
        if milestone_count >= 5:
            return "large"
        if milestone_count >= 2:
            return "medium"
        return "small"
