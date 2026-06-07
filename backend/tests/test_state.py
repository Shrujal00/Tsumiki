"""Tests for the shared UserState model and WorldState behaviour.

These lock the contract every agent in Task 2 reads/writes. If a field name or
type changes here, Tasks 2 and 3 break — that is intentional.
"""

from datetime import datetime

from state import WorldState, new_user_state


def test_new_user_state_is_empty_and_well_formed():
    state = new_user_state("user-123")

    assert state["user_id"] == "user-123"
    assert state["plan"] == []
    assert state["checkin_history"] == []
    assert state["reflection_notes"] == []
    assert state["streak"] == 0
    assert state["escalation_level"] == 0
    # A brand-new user has no goal, no check-in, no pending event yet.
    assert state["active_goal"] is None
    assert state["last_checkin_at"] is None
    assert state["pending_event"] is None

    ws = state["world_state"]
    assert isinstance(ws, WorldState)
    assert ws.stones == []
    assert ws.balance_level == 0


def test_new_user_state_instances_are_independent():
    # Mutating one factory result must not bleed into another (no shared defaults).
    a = new_user_state("a")
    b = new_user_state("b")

    a["world_state"].add_stone("small")
    a["plan"].append({"x": 1})

    assert b["world_state"].stones == []
    assert b["plan"] == []


def test_add_stone_appends_with_correct_variant():
    ws = WorldState(stones=[], balance_level=0)

    ws.add_stone("small")

    assert len(ws.stones) == 1
    stone = ws.stones[0]
    assert stone["variant"] == "small"
    assert stone["from_user_id"] is None
    assert isinstance(stone["created_at"], datetime)


def test_add_stone_records_gifting_user():
    ws = WorldState(stones=[], balance_level=0)

    ws.add_stone("gifted", from_user="friend-9")

    assert ws.stones[-1]["variant"] == "gifted"
    assert ws.stones[-1]["from_user_id"] == "friend-9"


def test_add_stone_appends_in_order():
    ws = WorldState(stones=[], balance_level=0)

    ws.add_stone("small")
    ws.add_stone("resilient")
    ws.add_stone("large")

    assert [s["variant"] for s in ws.stones] == ["small", "resilient", "large"]


def test_reinforce_balance_increments_predictably():
    ws = WorldState(stones=[], balance_level=0)

    ws.reinforce_balance()
    assert ws.balance_level == 1

    ws.reinforce_balance()
    ws.reinforce_balance()
    assert ws.balance_level == 3

    # Reinforcing balance must never create stones.
    assert ws.stones == []
