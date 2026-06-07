"""FastAPI routes for the client-facing flows (Task 3).

Thin HTTP layer over :class:`service.TsumikiService`. Pydantic models validate
every request and shape every response; missing users/goals return clear 4xx
errors. The service is provided via the ``get_service`` dependency so tests can
override it with a fully offline fake.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from service import TsumikiService, UserNotFoundError
from state import CheckIn, Goal, UserState, WorldState

router = APIRouter()

# Module-level default service (real deps, built lazily on first use). Tests
# override ``get_service`` so this is never constructed in the suite.
_default_service: Optional[TsumikiService] = None


def get_service() -> TsumikiService:
    global _default_service
    if _default_service is None:
        _default_service = TsumikiService()
    return _default_service


# --------------------------------------------------------------------------- #
# Request models                                                              #
# --------------------------------------------------------------------------- #
class MilestoneIn(BaseModel):
    description: str
    target_date: Optional[_date] = None
    completed: bool = False


class GoalRequest(BaseModel):
    title: str
    domain: str = ""
    target_date: Optional[_date] = None
    milestones: list[MilestoneIn] = Field(default_factory=list)


class CheckInRequest(BaseModel):
    action_id: str
    completed: bool
    note: Optional[str] = None
    timestamp: Optional[datetime] = None
    # Optional escalation context — supplied by the client (app) when available.
    phone_number: Optional[str] = None
    user_name: Optional[str] = None


class SupportRequest(BaseModel):
    from_user_id: str
    to_user_id: str
    difficulty: str = "small"


# --------------------------------------------------------------------------- #
# Response models                                                             #
# --------------------------------------------------------------------------- #
class StoneOut(BaseModel):
    variant: str
    created_at: Optional[datetime] = None
    from_user_id: Optional[str] = None


class WorldStateOut(BaseModel):
    balance_level: int
    stones: list[StoneOut]


class PlannedActionOut(BaseModel):
    date: Optional[_date] = None
    description: str
    estimated_effort: str = ""
    milestone_id: str = ""


class MilestoneOut(BaseModel):
    description: str
    target_date: Optional[_date] = None
    completed: bool = False


class GoalOut(BaseModel):
    title: str
    domain: str = ""
    target_date: Optional[_date] = None
    milestones: list[MilestoneOut] = Field(default_factory=list)


class AgentEventOut(BaseModel):
    type: str
    goal_id: str
    difficulty: str
    timestamp: Optional[datetime] = None
    from_user_id: Optional[str] = None


class CheckInOut(BaseModel):
    timestamp: Optional[datetime] = None
    action_id: str
    completed: bool
    note: Optional[str] = None


class UserStateOut(BaseModel):
    user_id: str
    active_goal: Optional[GoalOut] = None
    plan: list[PlannedActionOut] = Field(default_factory=list)
    checkin_history: list[CheckInOut] = Field(default_factory=list)
    streak: int = 0
    last_checkin_at: Optional[datetime] = None
    reflection_notes: list[str] = Field(default_factory=list)
    world_state: WorldStateOut
    pending_event: Optional[AgentEventOut] = None
    escalation_level: int = 0


class PlanResponse(BaseModel):
    active_goal: Optional[GoalOut] = None
    plan: list[PlannedActionOut]


class CallResultOut(BaseModel):
    id: Optional[str] = None
    status: str
    user_response_summary: Optional[str] = None


class CheckInResponse(BaseModel):
    world_state: WorldStateOut
    pending_event: Optional[AgentEventOut] = None
    escalation_level: int
    call_result: Optional[CallResultOut] = None


class ReflectionResponse(BaseModel):
    reflection_notes: list[str]


# --------------------------------------------------------------------------- #
# Serialization helpers (WorldState is a dataclass; the rest are TypedDicts)  #
# --------------------------------------------------------------------------- #
def _world_out(ws: WorldState | None) -> WorldStateOut:
    ws = ws or WorldState()
    return WorldStateOut(
        balance_level=ws.balance_level,
        stones=[StoneOut(**s) for s in ws.stones],
    )


def _goal_out(goal: Goal | None) -> Optional[GoalOut]:
    if not goal:
        return None
    return GoalOut(
        title=goal.get("title", ""),
        domain=goal.get("domain", "") or "",
        target_date=goal.get("target_date"),
        milestones=[MilestoneOut(**m) for m in (goal.get("milestones") or [])],
    )


def _state_out(state: UserState) -> UserStateOut:
    return UserStateOut(
        user_id=state["user_id"],
        active_goal=_goal_out(state.get("active_goal")),
        plan=[PlannedActionOut(**a) for a in (state.get("plan") or [])],
        checkin_history=[CheckInOut(**c) for c in (state.get("checkin_history") or [])],
        streak=state.get("streak", 0),
        last_checkin_at=state.get("last_checkin_at"),
        reflection_notes=list(state.get("reflection_notes") or []),
        world_state=_world_out(state.get("world_state")),
        pending_event=(
            AgentEventOut(**state["pending_event"])
            if state.get("pending_event")
            else None
        ),
        escalation_level=state.get("escalation_level", 0),
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #
@router.post("/users/{user_id}/goals", response_model=PlanResponse)
def create_goal(
    user_id: str,
    body: GoalRequest,
    service: TsumikiService = Depends(get_service),
) -> PlanResponse:
    """Create a goal, run the Planner, return the generated plan to confirm."""
    goal: Goal = {
        "title": body.title,
        "domain": body.domain,
        "target_date": body.target_date,
        "milestones": [
            {
                "description": m.description,
                "target_date": m.target_date,
                "completed": m.completed,
            }
            for m in body.milestones
        ],
    }
    state = service.create_goal(user_id, goal)
    return PlanResponse(
        active_goal=_goal_out(state.get("active_goal")),
        plan=[PlannedActionOut(**a) for a in (state.get("plan") or [])],
    )


@router.post("/users/{user_id}/checkins", response_model=CheckInResponse)
def create_checkin(
    user_id: str,
    body: CheckInRequest,
    service: TsumikiService = Depends(get_service),
) -> CheckInResponse:
    """Record a check-in; run the graph; return the new world + any event."""
    checkin: CheckIn = {
        "timestamp": body.timestamp or datetime.now(timezone.utc),
        "action_id": body.action_id,
        "completed": body.completed,
        "note": body.note,
    }
    try:
        out = service.record_checkin(
            user_id,
            checkin,
            phone_number=body.phone_number,
            user_name=body.user_name,
        )
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    state = out["state"]
    call = out["call_result"]
    return CheckInResponse(
        world_state=_world_out(state.get("world_state")),
        pending_event=(
            AgentEventOut(**state["pending_event"])
            if state.get("pending_event")
            else None
        ),
        escalation_level=state.get("escalation_level", 0),
        call_result=(
            CallResultOut(
                id=call.id,
                status=call.status,
                user_response_summary=call.user_response_summary,
            )
            if call
            else None
        ),
    )


@router.get("/users/{user_id}/state", response_model=UserStateOut)
def get_state(
    user_id: str,
    service: TsumikiService = Depends(get_service),
) -> UserStateOut:
    """Full current UserState (dashboard polls this alongside Supabase Realtime)."""
    try:
        state = service.get_state(user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return _state_out(state)


@router.post("/users/{user_id}/reflection", response_model=ReflectionResponse)
def trigger_reflection(
    user_id: str,
    service: TsumikiService = Depends(get_service),
) -> ReflectionResponse:
    """Manually run the periodic reflection pass (for on-demand demoing)."""
    try:
        state = service.run_reflection(user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return ReflectionResponse(reflection_notes=list(state.get("reflection_notes") or []))


@router.post("/circles/{circle_id}/support", response_model=WorldStateOut)
def send_support(
    circle_id: str,
    body: SupportRequest,
    service: TsumikiService = Depends(get_service),
) -> WorldStateOut:
    """Record a 'stone of support' → support_received event on the recipient."""
    try:
        state = service.send_support(
            circle_id, body.from_user_id, body.to_user_id, body.difficulty
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Recipient {body.to_user_id} not found"
        )
    return _world_out(state.get("world_state"))
