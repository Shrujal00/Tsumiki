"""End-to-end API tests — fully offline.

A real ``TsumikiService`` is wired to a fake relational store, a mocked Vapi
client, and agents backed by a fake LLM. No Ollama, no Supabase, no telephony.
The ``get_service`` dependency is overridden so the routes exercise real
serialization + service orchestration against the fakes.
"""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
from agents.accountability import AccountabilityAgent
from agents.game_master import GameMasterAgent
from agents.planner import PlannerAgent
from agents.reflection import ReflectionAgent
from integrations.vapi import CallResult, REQUIRED_VARIABLE_KEYS
from main import app
from service import TsumikiService
from state import new_user_state

BASE = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Fakes                                                                       #
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


class FakeVector:
    def __init__(self):
        self.added = []

    def query_similar(self, user_id, query_text, k=5):
        return []

    def add_reflection(self, user_id, text, metadata):
        self.added.append((user_id, text, metadata))


class FakeRelational:
    """In-memory stand-in for RelationalMemory keyed by user_id.

    Mirrors real semantics: check-in history is written only via append_checkin;
    save_user_state persists scalars + world (not history); get_user_state returns
    a fresh copy each call.
    """

    def __init__(self):
        self.states: dict = {}
        self.saved_goals: list = []
        self.reflection_notes_written: list = []

    def get_user_state(self, user_id):
        cur = self.states.get(user_id)
        if cur is None:
            return None
        st = dict(cur)
        st["checkin_history"] = list(cur["checkin_history"])
        st["plan"] = list(cur.get("plan") or [])
        return st

    def ensure_user(self, user_id, display_name=None):
        self.states.setdefault(user_id, new_user_state(user_id))

    def save_goal(self, user_id, goal):
        self.ensure_user(user_id)
        self.states[user_id]["active_goal"] = goal
        self.saved_goals.append((user_id, goal))
        return "goal-1"

    def append_checkin(self, user_id, checkin):
        self.ensure_user(user_id)
        self.states[user_id]["checkin_history"].append(checkin)

    def add_reflection_note(self, user_id, note, domain=None):
        self.reflection_notes_written.append((user_id, note, domain))

    def save_user_state(self, user_id, state):
        cur = self.states.setdefault(user_id, new_user_state(user_id))
        if state.get("world_state") is not None:
            cur["world_state"] = state["world_state"]
        cur["streak"] = state.get("streak", cur.get("streak", 0))
        cur["escalation_level"] = state.get("escalation_level", cur.get("escalation_level", 0))
        cur["last_checkin_at"] = state.get("last_checkin_at", cur.get("last_checkin_at"))
        if state.get("plan"):
            cur["plan"] = state["plan"]
        if state.get("active_goal"):
            cur["active_goal"] = state["active_goal"]
        # deliberately does not persist checkin_history


class FakeVapi:
    def __init__(self, result=None):
        self.calls = []
        self._result = result or CallResult(
            id="call-1", status="answered", user_response_summary="Will do tonight"
        )

    def place_escalation_call(self, user_id, phone_number, variables):
        # The exact-keys contract is enforced here too.
        assert set(variables) == REQUIRED_VARIABLE_KEYS
        self.calls.append((user_id, phone_number, variables))
        return self._result


def _ci(day, completed):
    return {
        "timestamp": BASE + timedelta(days=day),
        "action_id": f"a{day}",
        "completed": completed,
        "note": None,
    }


def _plan_value():
    return SimpleNamespace(
        milestones=[SimpleNamespace(description="A1 basics", target_date=date(2026, 7, 1))],
        actions=[
            SimpleNamespace(
                date=date(2026, 6, 9),
                description="Learn 10 greetings",
                estimated_effort="15 min",
                milestone_index=0,
            )
        ],
    )


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def fakes():
    rel = FakeRelational()
    vapi = FakeVapi()
    vector = FakeVector()
    service = TsumikiService(
        relational=rel,
        vapi=vapi,
        planner=PlannerAgent(llm=FakeLLM(_plan_value())),
        accountability=AccountabilityAgent(llm=FakeLLM(SimpleNamespace(message="warm note"))),
        game_master=GameMasterAgent(),
        reflection=ReflectionAgent(
            llm=FakeLLM(SimpleNamespace(insights=["~80% of misses fall on Mondays"])),
            vector=vector,
        ),
    )
    app.dependency_overrides[api.get_service] = lambda: service
    client = TestClient(app)
    yield SimpleNamespace(client=client, rel=rel, vapi=vapi, vector=vector, service=service)
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #
def test_create_goal_returns_plan(fakes):
    resp = fakes.client.post(
        "/users/u1/goals",
        json={
            "title": "Learn Spanish",
            "domain": "language",
            "target_date": "2026-09-01",
            "milestones": [{"description": "A1 basics", "target_date": "2026-07-01"}],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_goal"]["title"] == "Learn Spanish"
    assert len(body["plan"]) == 1
    assert body["plan"][0]["description"] == "Learn 10 greetings"
    assert fakes.rel.saved_goals  # goal was persisted


def test_checkin_completed_changes_world(fakes):
    # Seed user with a goal + plan so the check-in path is entered.
    st = new_user_state("u1")
    st["active_goal"] = {"title": "Learn Spanish", "domain": "language", "milestones": []}
    st["plan"] = [{"date": None, "description": "20-min Spanish", "estimated_effort": "20m", "milestone_id": "0"}]
    fakes.rel.states["u1"] = st

    resp = fakes.client.post(
        "/users/u1/checkins",
        json={"action_id": "0", "completed": True, "note": "done"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["world_state"]["balance_level"] == 1  # streak_maintained reinforced
    assert body["pending_event"] is None  # applied + cleared
    assert body["escalation_level"] == 0
    assert body["call_result"] is None
    assert fakes.vapi.calls == []  # no escalation, no call


def test_checkin_escalation_places_call_and_logs_outcome(fakes):
    st = new_user_state("u1")
    st["active_goal"] = {"title": "Learn Spanish", "domain": "language", "milestones": []}
    st["plan"] = [{"date": None, "description": "20-min Spanish", "estimated_effort": "20m", "milestone_id": "0"}]
    st["checkin_history"] = [_ci(0, False), _ci(1, False)]  # already two misses
    st["escalation_level"] = 1
    fakes.rel.states["u1"] = st

    resp = fakes.client.post(
        "/users/u1/checkins",
        json={
            "action_id": "2",
            "completed": False,
            "timestamp": (BASE + timedelta(days=2)).isoformat(),
            "phone_number": "+15555550123",
            "user_name": "Asha",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["escalation_level"] == 2
    assert body["call_result"]["status"] == "answered"
    # The closed feedback loop wrote the outcome back into memory.
    assert any("Voice escalation" in n for _, n, _ in fakes.rel.reflection_notes_written)
    # Variables were pulled live from state, not hardcoded.
    _, phone, variables = fakes.vapi.calls[0]
    assert phone == "+15555550123"
    assert variables["userName"] == "Asha"
    assert variables["goalName"] == "Learn Spanish"


def test_get_state_404_for_unknown_user(fakes):
    resp = fakes.client.get("/users/ghost/state")
    assert resp.status_code == 404


def test_get_state_returns_full_state(fakes):
    st = new_user_state("u9")
    st["streak"] = 3
    st["world_state"].add_stone("resilient")
    fakes.rel.states["u9"] = st

    resp = fakes.client.get("/users/u9/state")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == "u9"
    assert body["streak"] == 3
    assert body["world_state"]["stones"][0]["variant"] == "resilient"


def test_reflection_endpoint_appends_notes(fakes):
    st = new_user_state("u1")
    st["checkin_history"] = [_ci(0, False), _ci(7, False)]
    fakes.rel.states["u1"] = st

    resp = fakes.client.post("/users/u1/reflection")
    assert resp.status_code == 200, resp.text
    notes = resp.json()["reflection_notes"]
    assert any("Mondays" in n for n in notes)
    assert fakes.vector.added  # also written to the vector store


def test_reflection_404_for_unknown_user(fakes):
    assert fakes.client.post("/users/ghost/reflection").status_code == 404


def test_support_adds_gifted_stone(fakes):
    recipient = new_user_state("friend")
    fakes.rel.states["friend"] = recipient

    resp = fakes.client.post(
        "/circles/c1/support",
        json={"from_user_id": "u1", "to_user_id": "friend", "difficulty": "small"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stones"][-1]["variant"] == "gifted"
    assert body["stones"][-1]["from_user_id"] == "u1"


def test_support_404_for_unknown_recipient(fakes):
    resp = fakes.client.post(
        "/circles/c1/support",
        json={"from_user_id": "u1", "to_user_id": "ghost"},
    )
    assert resp.status_code == 404
