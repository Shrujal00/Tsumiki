"""Deterministic unit tests for the Tsumiki Engine (agents.md §7).

These are the demo-reliability guarantee: zero LLM, zero I/O, identical result on
every run. They assert the *exact* resulting ``world_state`` for all five declared
``EventType`` values. Run them repeatedly — they must never flake.
"""

from datetime import datetime, timezone

from engine.tsumiki_engine import apply_event, stone_variant_for
from state import AgentEvent, WorldState

TS = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


def _event(etype, difficulty="medium", **extra) -> AgentEvent:
    base: dict = {
        "type": etype,
        "goal_id": "goal-1",
        "difficulty": difficulty,
        "timestamp": TS,
    }
    base.update(extra)
    return base  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# stone_variant_for                                                           #
# --------------------------------------------------------------------------- #
def test_stone_variant_for_maps_each_difficulty():
    assert stone_variant_for("small") == "small"
    assert stone_variant_for("medium") == "medium"
    assert stone_variant_for("large") == "large"


# --------------------------------------------------------------------------- #
# apply_event — all five event types                                          #
# --------------------------------------------------------------------------- #
def test_milestone_reached_adds_stone_of_difficulty_variant():
    ws = WorldState()
    out = apply_event(ws, _event("milestone_reached", difficulty="large"))

    assert out is ws  # mutates and returns same object
    assert len(out.stones) == 1
    assert out.stones[0]["variant"] == "large"
    assert out.stones[0]["from_user_id"] is None
    assert out.balance_level == 0


def test_streak_maintained_reinforces_balance_only():
    ws = WorldState()
    out = apply_event(ws, _event("streak_maintained"))

    assert out.stones == []
    assert out.balance_level == 1


def test_setback_recovered_adds_resilient_stone():
    ws = WorldState()
    out = apply_event(ws, _event("setback_recovered"))

    assert len(out.stones) == 1
    assert out.stones[0]["variant"] == "resilient"
    assert out.balance_level == 0


def test_support_received_adds_gifted_stone_tagged_with_sender():
    ws = WorldState()
    out = apply_event(ws, _event("support_received", from_user_id="friend-42"))

    assert len(out.stones) == 1
    assert out.stones[0]["variant"] == "gifted"
    assert out.stones[0]["from_user_id"] == "friend-42"
    assert out.balance_level == 0


def test_comeback_detected_is_a_deterministic_no_op():
    # comeback_detected has no §7 branch: escalation reset lives in the
    # Accountability Agent, not the engine. World state is unchanged.
    ws = WorldState()
    out = apply_event(ws, _event("comeback_detected"))

    assert out.stones == []
    assert out.balance_level == 0


def test_repeated_events_accumulate_deterministically():
    ws = WorldState()
    apply_event(ws, _event("streak_maintained"))
    apply_event(ws, _event("streak_maintained"))
    apply_event(ws, _event("milestone_reached", difficulty="small"))
    apply_event(ws, _event("setback_recovered"))

    assert ws.balance_level == 2
    assert [s["variant"] for s in ws.stones] == ["small", "resilient"]
