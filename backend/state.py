"""Shared, typed state object for the Tsumiki agent graph.

Every agent node (Task 2) reads from and writes to a single ``UserState``. The
field names and types here ARE the contract — keep them in lock-step with
agents.md §0 and §4.

Design note: agents.md describes these as "TypedDict" structures. The pure-data
shapes (Goal, Milestone, PlannedAction, CheckIn, Stone, AgentEvent, UserState)
are TypedDicts. ``WorldState`` is the one exception — agents.md §7 calls methods
on it (``add_stone`` / ``reinforce_balance``) and returns it from ``apply_event``,
so it must be a real class, not a TypedDict.

IDs such as ``goal_id``, ``milestone_id``, ``action_id`` and ``from_user_id`` are
plain string references to rows in the relational store; the data models here do
not carry their own ``id`` field (that lives in Postgres as a UUID).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal, TypedDict

StoneVariant = Literal["small", "medium", "large", "resilient", "gifted"]
EventType = Literal[
    "milestone_reached",
    "streak_maintained",
    "setback_recovered",
    "comeback_detected",
    "support_received",
]
Difficulty = Literal["small", "medium", "large"]


class Milestone(TypedDict):
    description: str
    target_date: date
    completed: bool


class Goal(TypedDict):
    title: str
    domain: str
    target_date: date
    milestones: list[Milestone]


class PlannedAction(TypedDict):
    date: date
    description: str
    estimated_effort: str
    milestone_id: str


class CheckIn(TypedDict):
    timestamp: datetime
    action_id: str
    completed: bool
    note: str | None


class Stone(TypedDict):
    variant: StoneVariant
    created_at: datetime
    from_user_id: str | None


class AgentEvent(TypedDict):
    type: EventType
    goal_id: str
    difficulty: Difficulty
    timestamp: datetime


@dataclass
class WorldState:
    """The visible "garden": a stack of stones and a balance level.

    Mutated only by the deterministic Tsumiki Engine (Task 2) via these methods —
    never directly by an LLM.
    """

    stones: list[Stone] = field(default_factory=list)
    balance_level: int = 0

    def add_stone(self, variant: StoneVariant, from_user: str | None = None) -> Stone:
        """Append a stone of ``variant``. ``from_user`` tags gifted stones."""
        stone: Stone = {
            "variant": variant,
            "created_at": datetime.now(timezone.utc),
            "from_user_id": from_user,
        }
        self.stones.append(stone)
        return stone

    def reinforce_balance(self) -> None:
        """Strengthen the stack's balance by one (rewards maintained streaks)."""
        self.balance_level += 1


class UserState(TypedDict):
    user_id: str
    active_goal: Goal
    plan: list[PlannedAction]
    checkin_history: list[CheckIn]
    streak: int
    last_checkin_at: datetime
    reflection_notes: list[str]
    world_state: WorldState
    pending_event: AgentEvent | None
    escalation_level: int


def new_user_state(user_id: str) -> UserState:
    """Return a sensible empty/default state for a brand-new user.

    ``active_goal`` and ``last_checkin_at`` start as ``None`` because a new user
    has not set a goal or checked in yet. The annotations stay exactly as
    agents.md defines them; these fields are populated once the Planner runs and
    the first check-in lands.
    """
    return UserState(
        user_id=user_id,
        active_goal=None,  # type: ignore[typeddict-item]  # no goal until Planner runs
        plan=[],
        checkin_history=[],
        streak=0,
        last_checkin_at=None,  # type: ignore[typeddict-item]  # never checked in yet
        reflection_notes=[],
        world_state=WorldState(),
        pending_event=None,
        escalation_level=0,
    )
