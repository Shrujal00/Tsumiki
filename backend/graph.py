"""LangGraph wiring for the Tsumiki agent graph.

Three compiled graphs / entry points:

* **Planning** — ``planner`` only.
* **Check-in** — ``accountability`` → (conditional) ``game_master`` →
  ``tsumiki_engine``. Accountability is only entered when there is an active plan
  and a check-in to evaluate; the Game Master / Engine are only entered when a
  ``pending_event`` has been emitted.
* **Reflection** — ``reflection`` only, on a SEPARATE entry point because it runs
  periodically, not per-interaction (agents.md §3).

The Tsumiki Engine is a plain function node (deterministic, "not an agent") that
consumes ``pending_event``, applies it to ``world_state`` via the pure
``engine.tsumiki_engine.apply_event``, and clears the event.

Public callables: ``run_planning_cycle``, ``run_checkin_cycle``,
``run_reflection_cycle``.

State note: the graph runs on ``GraphState``, a superset of the canonical
``UserState`` (state.py, the locked contract) plus two transient channels the
nodes emit — ``intervention_message`` and ``place_voice_call``. ``UserState`` in
state.py is intentionally left untouched.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from agents.accountability import AccountabilityAgent
from agents.game_master import GameMasterAgent
from agents.planner import PlannerAgent
from agents.reflection import ReflectionAgent
from engine.tsumiki_engine import apply_event
from state import CheckIn, Goal, UserState, new_user_state


class GraphState(UserState, total=False):
    """``UserState`` plus transient, node-emitted channels (not persisted)."""

    intervention_message: str
    place_voice_call: bool


# --------------------------------------------------------------------------- #
# LangSmith tracing — make each node transition a separate, inspectable step.  #
# --------------------------------------------------------------------------- #
def configure_tracing() -> None:
    """Export LangSmith env vars from config if tracing is requested.

    Respects ``LANGSMITH_TRACING``: if it is truthy in the environment, the
    LangSmith SDK auto-traces every LangChain/LangGraph node. We backfill the API
    key and project from config so the run lands in the ``tsumiki-dev`` project.
    Never raises — tracing is best-effort and must not block agent execution
    (e.g. in tests with no real key).
    """
    if os.environ.get("LANGSMITH_TRACING", "").lower() not in ("1", "true", "yes"):
        return
    try:
        from config import get_settings

        settings = get_settings()
        os.environ.setdefault(
            "LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY.get_secret_value()
        )
        os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)
    except Exception:  # noqa: BLE001 — tracing is optional, never fatal
        pass


# --------------------------------------------------------------------------- #
# Tsumiki Engine node (plain function — deterministic, not an "agent")         #
# --------------------------------------------------------------------------- #
def tsumiki_engine_node(state: GraphState) -> dict:
    """Apply ``pending_event`` to ``world_state`` and clear it."""
    event = state.get("pending_event")
    if event is None:
        return {}
    world = apply_event(state["world_state"], event)
    return {"world_state": world, "pending_event": None}


# --------------------------------------------------------------------------- #
# Graph builders                                                              #
# --------------------------------------------------------------------------- #
def build_planning_graph(planner: PlannerAgent | None = None):
    planner = planner or PlannerAgent()
    g = StateGraph(GraphState)
    g.add_node("planner", planner)
    g.add_edge(START, "planner")
    g.add_edge("planner", END)
    return g.compile()


def build_checkin_graph(
    accountability: AccountabilityAgent | None = None,
    game_master: GameMasterAgent | None = None,
):
    accountability = accountability or AccountabilityAgent()
    game_master = game_master or GameMasterAgent()

    g = StateGraph(GraphState)
    g.add_node("accountability", accountability)
    g.add_node("game_master", game_master)
    g.add_node("tsumiki_engine", tsumiki_engine_node)

    def route_start(state: GraphState) -> str:
        # Only evaluate adherence when there is an active goal AND a check-in to
        # judge. agents.md frames this as "an active plan + a check-in", but plans
        # are not persisted (no plans table — Task 1), so a freshly loaded state
        # always has plan=[]; gating on the persisted active_goal keeps the
        # check-in path working in production while preserving the same intent.
        if state.get("active_goal") and state.get("checkin_history"):
            return "accountability"
        return END

    g.add_conditional_edges(
        START, route_start, {"accountability": "accountability", END: END}
    )

    def route_after_accountability(state: GraphState) -> str:
        # Only touch the world when an event was actually emitted.
        return "game_master" if state.get("pending_event") else END

    g.add_conditional_edges(
        "accountability",
        route_after_accountability,
        {"game_master": "game_master", END: END},
    )
    g.add_edge("game_master", "tsumiki_engine")
    g.add_edge("tsumiki_engine", END)
    return g.compile()


def build_reflection_graph(reflection: ReflectionAgent | None = None):
    reflection = reflection or ReflectionAgent()
    g = StateGraph(GraphState)
    g.add_node("reflection", reflection)
    g.add_edge(START, "reflection")
    g.add_edge("reflection", END)
    return g.compile()


def build_support_graph(game_master: GameMasterAgent | None = None):
    """Game Master → Engine, for a pre-set ``support_received`` event."""
    game_master = game_master or GameMasterAgent()
    g = StateGraph(GraphState)
    g.add_node("game_master", game_master)
    g.add_node("tsumiki_engine", tsumiki_engine_node)
    g.add_edge(START, "game_master")
    g.add_edge("game_master", "tsumiki_engine")
    g.add_edge("tsumiki_engine", END)
    return g.compile()


# --------------------------------------------------------------------------- #
# State load/save helpers                                                     #
# --------------------------------------------------------------------------- #
def _resolve_relational(relational: Any, state: Optional[UserState]) -> Any:
    """Build a real RelationalMemory only when one is needed and not injected.

    When the caller injects ``state`` (tests, or already-loaded state) and no
    ``relational``, we stay fully offline: load is skipped and we do not persist.
    """
    if relational is not None:
        return relational
    if state is None:
        from memory.relational import RelationalMemory  # lazy

        return RelationalMemory()
    return None


def _load_state(user_id: str, relational: Any, state: Optional[UserState]) -> UserState:
    if state is not None:
        return state
    if relational is not None:
        loaded = relational.get_user_state(user_id)
        if loaded is not None:
            return loaded
    return new_user_state(user_id)


# --------------------------------------------------------------------------- #
# Public cycle callables                                                      #
# --------------------------------------------------------------------------- #
def run_planning_cycle(
    user_id: str,
    goal: Goal,
    *,
    relational: Any = None,
    state: Optional[UserState] = None,
    planner: PlannerAgent | None = None,
) -> UserState:
    """Generate a plan for ``goal`` and return the updated state."""
    configure_tracing()
    relational = _resolve_relational(relational, state)
    state = _load_state(user_id, relational, state)
    state["active_goal"] = goal

    result = build_planning_graph(planner).invoke(state)

    if relational is not None:
        relational.save_user_state(user_id, result)
    return result  # type: ignore[return-value]


def run_checkin_cycle(
    user_id: str,
    checkin: CheckIn,
    *,
    relational: Any = None,
    state: Optional[UserState] = None,
    accountability: AccountabilityAgent | None = None,
    game_master: GameMasterAgent | None = None,
) -> UserState:
    """Evaluate one ``checkin`` end-to-end; returns state with updated world."""
    configure_tracing()
    relational = _resolve_relational(relational, state)
    state = _load_state(user_id, relational, state)

    # Record the check-in onto the working state before evaluation.
    state["checkin_history"] = [*(state.get("checkin_history") or []), checkin]
    state["last_checkin_at"] = checkin.get("timestamp")

    result = build_checkin_graph(accountability, game_master).invoke(state)

    if relational is not None:
        relational.append_checkin(user_id, checkin)
        relational.save_user_state(user_id, result)
    return result  # type: ignore[return-value]


def run_reflection_cycle(
    user_id: str,
    *,
    relational: Any = None,
    state: Optional[UserState] = None,
    reflection: ReflectionAgent | None = None,
) -> UserState:
    """Run the periodic reflection pass; returns state with new notes."""
    configure_tracing()
    relational = _resolve_relational(relational, state)
    state = _load_state(user_id, relational, state)

    result = build_reflection_graph(reflection).invoke(state)

    if relational is not None:
        relational.save_user_state(user_id, result)
    return result  # type: ignore[return-value]


def run_support_cycle(
    to_user_id: str,
    from_user_id: str,
    *,
    difficulty: str = "small",
    relational: Any = None,
    state: Optional[UserState] = None,
    game_master: GameMasterAgent | None = None,
) -> UserState:
    """Apply a "stone of support" to the recipient's world and persist it."""
    configure_tracing()
    relational = _resolve_relational(relational, state)
    state = _load_state(to_user_id, relational, state)

    goal = state.get("active_goal") or {}
    state["pending_event"] = {  # type: ignore[typeddict-unknown-key]
        "type": "support_received",
        "goal_id": goal.get("title", ""),
        "difficulty": difficulty,
        "timestamp": datetime.now(timezone.utc),
        "from_user_id": from_user_id,
    }

    result = build_support_graph(game_master).invoke(state)

    if relational is not None:
        relational.save_user_state(to_user_id, result)
    return result  # type: ignore[return-value]
