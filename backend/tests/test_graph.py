"""Integration tests for the wired LangGraph cycles (graph.py).

All LLM calls are faked — no network, no Ollama, no Supabase. The check-in
integration test proves the headline acceptance criterion: a full
``run_checkin_cycle`` produces a UserState with a *visibly changed* ``world_state``
and a correctly cleared ``pending_event``, flowing Accountability → Game Master →
Tsumiki Engine.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace

from agents.accountability import AccountabilityAgent
from agents.game_master import GameMasterAgent
from agents.planner import PlannerAgent
from graph import run_checkin_cycle, run_planning_cycle
from state import CheckIn, Goal, WorldState, new_user_state

TS = datetime(2026, 6, 8, 8, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Fake LLM infrastructure                                                     #
# --------------------------------------------------------------------------- #
class _FakeStructured:
    def __init__(self, value):
        self._value = value

    def invoke(self, messages):
        return self._value


class FakeLLM:
    def __init__(self, value):
        self._value = value

    def with_structured_output(self, schema):
        return _FakeStructured(self._value)


def _goal() -> Goal:
    return Goal(
        title="Learn Spanish",
        domain="language",
        target_date=date(2026, 9, 1),
        milestones=[
            {"description": "A1 basics", "target_date": date(2026, 7, 1), "completed": False},
            {"description": "Hold a 5-min convo", "target_date": date(2026, 8, 1), "completed": False},
        ],
    )


# --------------------------------------------------------------------------- #
# Check-in cycle — the headline integration test                             #
# --------------------------------------------------------------------------- #
def test_run_checkin_cycle_changes_world_state_and_clears_event():
    state = new_user_state("u1")
    state["active_goal"] = _goal()
    state["plan"] = [
        {
            "date": date(2026, 6, 8),
            "description": "20-min Spanish session",
            "estimated_effort": "20 min",
            "milestone_id": "0",
        }
    ]

    # On-time completed check-in → streak_maintained → engine reinforces balance.
    checkin: CheckIn = {
        "timestamp": TS,
        "action_id": "0",
        "completed": True,
        "note": "done",
    }

    # Inject a fake LLM (acceptance: "mocked LLM"); the on-time path won't call it,
    # but injecting proves no accidental network dependency.
    acct = AccountabilityAgent(llm=FakeLLM(SimpleNamespace(message="great work!")))

    result = run_checkin_cycle(
        "u1",
        checkin,
        state=state,
        accountability=acct,
        game_master=GameMasterAgent(),
    )

    # World visibly changed: a maintained streak reinforced balance 0 -> 1.
    assert isinstance(result["world_state"], WorldState)
    assert result["world_state"].balance_level == 1
    # Event was applied then cleared.
    assert result["pending_event"] is None
    # The check-in was recorded on the working state.
    assert len(result["checkin_history"]) == 1


def test_run_checkin_cycle_no_plan_is_a_noop_on_world():
    # No plan → route_start sends straight to END; world untouched.
    state = new_user_state("u2")  # no active_goal, no plan
    checkin: CheckIn = {
        "timestamp": TS,
        "action_id": "x",
        "completed": True,
        "note": None,
    }
    result = run_checkin_cycle("u2", checkin, state=state)

    assert result["world_state"].balance_level == 0
    assert result["world_state"].stones == []
    assert result["pending_event"] is None


# --------------------------------------------------------------------------- #
# Planning cycle — structured plan is written back to state                   #
# --------------------------------------------------------------------------- #
def test_run_planning_cycle_writes_structured_plan():
    plan_value = SimpleNamespace(
        milestones=[
            SimpleNamespace(description="A1 basics", target_date=date(2026, 7, 1)),
        ],
        actions=[
            SimpleNamespace(
                date=date(2026, 6, 9),
                description="Learn 10 greetings",
                estimated_effort="15 min",
                milestone_index=0,
            ),
            SimpleNamespace(
                date=date(2026, 6, 10),
                description="Practice numbers 1-20",
                estimated_effort="15 min",
                milestone_index=0,
            ),
        ],
    )
    planner = PlannerAgent(llm=FakeLLM(plan_value))

    state = new_user_state("u3")
    result = run_planning_cycle("u3", _goal(), state=state, planner=planner)

    assert len(result["plan"]) == 2
    assert result["plan"][0]["description"] == "Learn 10 greetings"
    assert result["plan"][0]["milestone_id"] == "0"
    assert result["plan"][0]["estimated_effort"] == "15 min"
