"""Planner Agent (agents.md §1).

Converts a high-level ``active_goal`` into a concrete, time-boxed plan: milestones
plus a first week of ``PlannedAction``s. Crucially, if ``reflection_notes`` exist
from prior cycles, the prompt *explicitly* instructs the model to route the plan
around those known friction points before they recur. That instruction is the
literal proof that "the system remembers and adapts" — it is not optional.

The LLM call uses structured output (``with_structured_output`` + a Pydantic
schema), never free-text parsing.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Any

from pydantic import BaseModel, Field

from agents.llm import build_chat_model
from state import Goal, PlannedAction, UserState


# --------------------------------------------------------------------------- #
# Structured-output schema (what the model must return)                       #
# --------------------------------------------------------------------------- #
class _PlanMilestone(BaseModel):
    description: str = Field(description="A concrete, checkable milestone")
    target_date: _date = Field(description="Realistic ISO date for this milestone")


class _PlanAction(BaseModel):
    date: _date = Field(description="ISO date this action is scheduled for")
    description: str = Field(description="A specific, doable action for that day")
    estimated_effort: str = Field(description="e.g. '20 min', 'light', '1 hour'")
    milestone_index: int = Field(
        description="0-based index of the milestone this action serves"
    )


class _PlanOutput(BaseModel):
    milestones: list[_PlanMilestone]
    actions: list[_PlanAction] = Field(
        description="The first week of concrete daily/weekly actions"
    )


_SYSTEM = (
    "You are Tsumiki's Planner. You turn a user's goal into a realistic, calm, "
    "time-boxed plan: a short list of milestones with target dates, and the first "
    "week of specific daily/weekly actions. Keep actions small and achievable. "
    "Never schedule demanding back-to-back sessions. Each action must reference the "
    "milestone it serves by its 0-based index."
)


class PlannerAgent:
    """LangGraph node: ``(state) -> {plan, active_goal}`` update."""

    def __init__(self, model: str | None = None, llm: Any | None = None) -> None:
        self._model = model
        self._llm = llm  # inject a fake in tests to avoid network/config

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = build_chat_model(self._model)
        return self._llm

    # ----- prompt ------------------------------------------------------- #
    @staticmethod
    def _build_human_prompt(goal: Goal, reflection_notes: list[str]) -> str:
        ms = goal.get("milestones") or []
        lines = [
            f"Goal: {goal.get('title')}",
            f"Domain: {goal.get('domain')}",
            f"Target date: {goal.get('target_date')}",
        ]
        if ms:
            lines.append("Known milestones:")
            lines += [f"  - {m.get('description')} (by {m.get('target_date')})" for m in ms]

        if reflection_notes:
            # THE adaptation instruction. This is what makes the plan feel like it
            # knows the user. Do not soften or remove.
            lines.append(
                "\nIMPORTANT — the system has learned the following about this user "
                "from past cycles. Route the plan AROUND these friction points BEFORE "
                "they recur (e.g. if Mondays are historically missed, do not schedule "
                "demanding sessions on Mondays; prefer the user's strong time slots):"
            )
            lines += [f"  - {note}" for note in reflection_notes]
        else:
            lines.append(
                "\nNo prior reflection notes exist yet; plan from sensible defaults."
            )
        return "\n".join(lines)

    # ----- node --------------------------------------------------------- #
    def __call__(self, state: UserState) -> dict:
        goal = state.get("active_goal")
        if goal is None:
            return {}  # nothing to plan without a goal

        reflection_notes = state.get("reflection_notes") or []
        human = self._build_human_prompt(goal, reflection_notes)

        structured = self.llm.with_structured_output(_PlanOutput)
        result: _PlanOutput = structured.invoke(
            [("system", _SYSTEM), ("human", human)]
        )

        plan: list[PlannedAction] = [
            PlannedAction(
                date=a.date,
                description=a.description,
                estimated_effort=a.estimated_effort,
                # milestone_index -> a stable string ref the relational store can map
                milestone_id=str(a.milestone_index),
            )
            for a in result.actions
        ]

        # Reflect any LLM-proposed milestones back onto the goal so downstream
        # cycles (and the relational store) see them.
        updated_goal: Goal = {
            **goal,
            "milestones": [
                {
                    "description": m.description,
                    "target_date": m.target_date,
                    "completed": False,
                }
                for m in result.milestones
            ]
            or goal.get("milestones", []),
        }

        return {"plan": plan, "active_goal": updated_goal}
