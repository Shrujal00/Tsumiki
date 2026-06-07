"""TsumikiService — orchestration seam between the API and the agent graph.

Wraps the LangGraph cycle callables, the relational store, and the Vapi client
behind a small set of intent methods the FastAPI routers call. Everything is
injectable so the API test suite runs fully offline (fake relational, mocked
Vapi, agents with a fake LLM) — no Ollama, no Supabase, no telephony.

Persistence rule (Supabase Realtime readiness): every state-changing method
writes through ``RelationalMemory`` so the dashboard's Realtime subscriptions see
the change. No write lives only in process memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from graph import (
    run_checkin_cycle,
    run_planning_cycle,
    run_reflection_cycle,
    run_support_cycle,
)
from integrations.vapi import CallResult, build_call_variables
from state import CheckIn, Goal, UserState


class UserNotFoundError(Exception):
    """Raised when an operation targets a user with no persisted state."""


class TsumikiService:
    """Application service used by the API layer and the demo scripts."""

    def __init__(
        self,
        relational: Any | None = None,
        vapi: Any | None = None,
        planner: Any | None = None,
        accountability: Any | None = None,
        game_master: Any | None = None,
        reflection: Any | None = None,
    ) -> None:
        self._relational = relational
        self._vapi = vapi
        self.planner = planner
        self.accountability = accountability
        self.game_master = game_master
        self.reflection = reflection

    # ----- lazy real dependencies -------------------------------------- #
    @property
    def relational(self) -> Any:
        if self._relational is None:
            from memory.relational import RelationalMemory  # lazy

            self._relational = RelationalMemory()
        return self._relational

    @property
    def vapi(self) -> Any:
        if self._vapi is None:
            from integrations.vapi import VapiClient  # lazy

            self._vapi = VapiClient()
        return self._vapi

    # ----- goals ------------------------------------------------------- #
    def create_goal(self, user_id: str, goal: Goal) -> UserState:
        """Persist the goal + run the planning cycle; returns state with plan."""
        self.relational.ensure_user(user_id)
        self.relational.save_goal(user_id, goal)  # owns goals/milestones
        return run_planning_cycle(
            user_id, goal, relational=self.relational, planner=self.planner
        )

    # ----- check-ins (with voice escalation hook) ---------------------- #
    def record_checkin(
        self,
        user_id: str,
        checkin: CheckIn,
        *,
        phone_number: str | None = None,
        user_name: str | None = None,
    ) -> dict:
        """Record a check-in end-to-end. Returns ``{state, call_result}``.

        The agent graph persists the check-in + world snapshot. If the
        deterministic ladder escalated to level 2 *and* a phone number is
        available, an escalation call is placed and its outcome is logged back
        into memory (the closed feedback loop).
        """
        state = run_checkin_cycle(
            user_id,
            checkin,
            relational=self.relational,
            accountability=self.accountability,
            game_master=self.game_master,
        )

        call_result: Optional[CallResult] = None
        if state.get("escalation_level") == 2 and state.get("place_voice_call"):
            call_result = self._maybe_place_call(
                user_id, state, phone_number, user_name
            )

        return {"state": state, "call_result": call_result}

    def _maybe_place_call(
        self,
        user_id: str,
        state: UserState,
        phone_number: str | None,
        user_name: str | None,
    ) -> Optional[CallResult]:
        if not phone_number:
            # No number to dial — record that escalation was warranted anyway.
            self._log_call_outcome(
                user_id,
                CallResult(id=None, status="skipped_no_phone_number"),
            )
            return None

        variables = build_call_variables(state, user_name=user_name)
        result = self.vapi.place_escalation_call(user_id, phone_number, variables)
        self._log_call_outcome(user_id, result)
        return result

    def _log_call_outcome(self, user_id: str, result: CallResult) -> None:
        """Closed feedback loop (agents.md §5): write the outcome to memory."""
        note = f"Voice escalation call — status={result.status}."
        if result.user_response_summary:
            note += f" Response: {result.user_response_summary}"

        now = datetime.now(timezone.utc)
        self.relational.append_checkin(
            user_id,
            CheckIn(
                timestamp=now,
                action_id="voice_escalation",
                completed=False,
                note=note,
            ),
        )
        self.relational.add_reflection_note(user_id, note, domain="escalation")

    # ----- state read -------------------------------------------------- #
    def get_state(self, user_id: str) -> UserState:
        state = self.relational.get_user_state(user_id)
        if state is None:
            raise UserNotFoundError(user_id)
        return state

    # ----- reflection -------------------------------------------------- #
    def run_reflection(self, user_id: str) -> UserState:
        if self.relational.get_user_state(user_id) is None:
            raise UserNotFoundError(user_id)
        return run_reflection_cycle(
            user_id, relational=self.relational, reflection=self.reflection
        )

    # ----- shared circles: stone of support ---------------------------- #
    def send_support(
        self,
        circle_id: str,
        from_user_id: str,
        to_user_id: str,
        difficulty: str = "small",
    ) -> UserState:
        """Apply a ``support_received`` stone to the recipient's world."""
        if self.relational.get_user_state(to_user_id) is None:
            raise UserNotFoundError(to_user_id)
        return run_support_cycle(
            to_user_id,
            from_user_id,
            difficulty=difficulty,
            relational=self.relational,
            game_master=self.game_master,
        )
