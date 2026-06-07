"""Tests for the hybrid memory layer.

The real Supabase and Chroma clients are never touched. RelationalMemory and
VectorMemory both accept an injected client/collection, so we pass in fakes and
assert the *contract* with the underlying client (which table, which call, what
payload) plus correct (de)serialization and empty/missing-user handling.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from memory.relational import RelationalMemory
from memory.vector import VectorMemory
from state import new_user_state


# --------------------------------------------------------------------------- #
# Fake Supabase client (chainable query builder, records calls, returns data)  #
# --------------------------------------------------------------------------- #
class _FakeQuery:
    def __init__(self, recorder, table):
        self._rec = recorder
        self._table = table

    # query builder methods are chainable no-ops that just return self
    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, payload):
        self._rec.calls.append((self._table, "insert", payload))
        return self

    def upsert(self, payload):
        self._rec.calls.append((self._table, "upsert", payload))
        return self

    def execute(self):
        return SimpleNamespace(data=self._rec.data.get(self._table, []))


class FakeSupabase:
    def __init__(self, data=None):
        self.data = data or {}
        self.calls = []

    def table(self, name):
        self.calls.append((name, "table", None))
        return _FakeQuery(self, name)


# --------------------------------------------------------------------------- #
# RelationalMemory                                                             #
# --------------------------------------------------------------------------- #
def test_get_checkin_history_queries_checkins_and_maps_rows():
    fake = FakeSupabase(
        data={
            "checkins": [
                {
                    "action_id": "a1",
                    "completed": True,
                    "note": "done",
                    "timestamp": "2026-06-01T08:00:00+00:00",
                },
                {
                    "action_id": "a2",
                    "completed": False,
                    "note": None,
                    "timestamp": "2026-06-02T08:00:00+00:00",
                },
            ]
        }
    )
    mem = RelationalMemory(client=fake)

    history = mem.get_checkin_history("u1", limit=10)

    assert ("checkins", "table", None) in fake.calls
    assert len(history) == 2
    assert history[0]["action_id"] == "a1"
    assert history[0]["completed"] is True
    assert history[0]["note"] == "done"
    assert isinstance(history[0]["timestamp"], datetime)
    assert history[1]["note"] is None


def test_get_checkin_history_empty_when_no_rows():
    mem = RelationalMemory(client=FakeSupabase(data={}))
    assert mem.get_checkin_history("u1") == []


def test_append_checkin_inserts_serialized_row():
    fake = FakeSupabase()
    mem = RelationalMemory(client=fake)
    checkin = {
        "timestamp": datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
        "action_id": "a1",
        "completed": True,
        "note": "great",
    }

    mem.append_checkin("u1", checkin)

    inserts = [c for c in fake.calls if c[1] == "insert"]
    assert len(inserts) == 1
    table, _, payload = inserts[0]
    assert table == "checkins"
    assert payload["user_id"] == "u1"
    assert payload["action_id"] == "a1"
    assert payload["completed"] is True
    assert payload["note"] == "great"
    # datetime must be serialized to an ISO string for JSON transport
    assert payload["timestamp"] == "2026-06-01T08:00:00+00:00"


def test_get_user_state_missing_user_returns_none():
    mem = RelationalMemory(client=FakeSupabase(data={"users": []}))
    assert mem.get_user_state("nobody") is None


def test_get_user_state_assembles_full_state():
    fake = FakeSupabase(
        data={
            "users": [
                {
                    "id": "u1",
                    "streak": 4,
                    "escalation_level": 1,
                    "last_checkin_at": "2026-06-05T07:00:00+00:00",
                }
            ],
            "checkins": [
                {
                    "action_id": "a1",
                    "completed": True,
                    "note": None,
                    "timestamp": "2026-06-05T07:00:00+00:00",
                }
            ],
            "world_states": [
                {
                    "balance_level": 3,
                    "stones": [
                        {
                            "variant": "small",
                            "created_at": "2026-06-01T00:00:00+00:00",
                            "from_user_id": None,
                        }
                    ],
                }
            ],
            "reflection_notes": [{"note": "mornings work best"}],
            "goals": [
                {
                    "id": "g1",
                    "title": "Learn Spanish",
                    "domain": "language",
                    "target_date": "2026-12-31",
                }
            ],
            "milestones": [
                {
                    "description": "Reach A1 level",
                    "target_date": "2026-08-01",
                    "completed": False,
                }
            ],
        }
    )
    mem = RelationalMemory(client=fake)

    state = mem.get_user_state("u1")

    assert state is not None
    assert state["user_id"] == "u1"
    assert state["streak"] == 4
    assert state["escalation_level"] == 1
    assert isinstance(state["last_checkin_at"], datetime)
    # world_state
    assert state["world_state"].balance_level == 3
    assert len(state["world_state"].stones) == 1
    assert state["world_state"].stones[0]["variant"] == "small"
    assert isinstance(state["world_state"].stones[0]["created_at"], datetime)
    # reflections + checkins
    assert state["reflection_notes"] == ["mornings work best"]
    assert len(state["checkin_history"]) == 1
    # active goal + milestones
    assert state["active_goal"]["title"] == "Learn Spanish"
    assert isinstance(state["active_goal"]["target_date"], date)
    assert len(state["active_goal"]["milestones"]) == 1
    assert state["active_goal"]["milestones"][0]["description"] == "Reach A1 level"


def test_save_user_state_upserts_users_and_world_state():
    fake = FakeSupabase()
    mem = RelationalMemory(client=fake)
    state = new_user_state("u1")
    state["streak"] = 5
    state["escalation_level"] = 2
    state["world_state"].add_stone("large")
    state["world_state"].reinforce_balance()

    mem.save_user_state("u1", state)

    upserts = [c for c in fake.calls if c[1] == "upsert"]
    tables = [t for (t, _, _) in upserts]
    assert "users" in tables
    assert "world_states" in tables

    users_payload = next(p for (t, _, p) in upserts if t == "users")
    assert users_payload["id"] == "u1"
    assert users_payload["streak"] == 5
    assert users_payload["escalation_level"] == 2

    world_payload = next(p for (t, _, p) in upserts if t == "world_states")
    assert world_payload["user_id"] == "u1"
    assert world_payload["balance_level"] == 1
    assert world_payload["stones"][0]["variant"] == "large"
    # stone datetime serialized to ISO string for jsonb storage
    assert isinstance(world_payload["stones"][0]["created_at"], str)


# --------------------------------------------------------------------------- #
# VectorMemory                                                                 #
# --------------------------------------------------------------------------- #
def test_add_reflection_calls_collection_add_with_user_metadata():
    col = MagicMock()
    vm = VectorMemory(collection=col)

    vm.add_reflection("u1", "felt drained after work", {"domain": "fitness"})

    col.add.assert_called_once()
    kwargs = col.add.call_args.kwargs
    assert kwargs["documents"] == ["felt drained after work"]
    assert kwargs["metadatas"][0]["user_id"] == "u1"
    assert kwargs["metadatas"][0]["domain"] == "fitness"
    assert len(kwargs["ids"]) == 1


def test_query_similar_returns_flat_documents_scoped_to_user():
    col = MagicMock()
    col.query.return_value = {"documents": [["a", "b", "c"]]}
    vm = VectorMemory(collection=col)

    res = vm.query_similar("u1", "mornings", k=3)

    assert res == ["a", "b", "c"]
    kwargs = col.query.call_args.kwargs
    assert kwargs["query_texts"] == ["mornings"]
    assert kwargs["n_results"] == 3
    assert kwargs["where"] == {"user_id": "u1"}


def test_query_similar_empty_results():
    col = MagicMock()
    col.query.return_value = {"documents": [[]]}
    vm = VectorMemory(collection=col)
    assert vm.query_similar("u1", "anything") == []


def test_query_similar_handles_missing_documents_key():
    col = MagicMock()
    col.query.return_value = {}
    vm = VectorMemory(collection=col)
    assert vm.query_similar("u1", "anything") == []
