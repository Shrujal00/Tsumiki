"""Unit tests for the Accountability escalation ladder (agents.md §2).

The *decision* is tested in complete isolation from the LLM: ``decide_escalation``
is a pure function, so no mock is even needed for it. All five rows of the §2
ladder table are covered. The node's LLM call (wording only) is exercised
separately with a fully faked LLM, asserting the deterministic/​probabilistic split:
the model is consulted ONLY for text, never for the escalation decision.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from agents.accountability import AccountabilityAgent, decide_escalation
from state import CheckIn

BASE = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def _ci(day_offset: int, completed: bool) -> CheckIn:
    return CheckIn(
        timestamp=BASE + timedelta(days=day_offset),
        action_id=f"a{day_offset}",
        completed=completed,
        note=None,
    )


# --------------------------------------------------------------------------- #
# decide_escalation — all 5 rows of the ladder                                #
# --------------------------------------------------------------------------- #
def test_row1_on_time_emits_streak_maintained():
    history = [_ci(0, True), _ci(1, True)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=0)
    assert d.rung == "on_time"
    assert d.escalation_level == 0
    assert d.event_type == "streak_maintained"
    assert d.place_voice_call is False


def test_row2_one_miss_keeps_level_no_event():
    history = [_ci(0, True), _ci(1, False)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=0)
    assert d.rung == "one_miss"
    assert d.escalation_level == 0
    assert d.event_type is None
    assert d.place_voice_call is False


def test_row3_two_misses_escalates_to_level_1():
    history = [_ci(0, True), _ci(1, False), _ci(2, False)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=0)
    assert d.rung == "two_misses"
    assert d.escalation_level == 1
    assert d.event_type is None
    assert d.place_voice_call is False


def test_row4_three_plus_misses_escalates_to_level_2_with_voice_call():
    history = [_ci(0, False), _ci(1, False), _ci(2, False)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=1)
    assert d.rung == "three_plus"
    assert d.escalation_level == 2
    assert d.event_type is None
    assert d.place_voice_call is True


def test_row5_comeback_resets_level_and_emits_comeback_detected():
    # Was escalated (level 2); user resumes with a completed check-in.
    history = [_ci(0, False), _ci(1, False), _ci(2, True)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=2)
    assert d.rung == "comeback"
    assert d.escalation_level == 0
    assert d.event_type == "comeback_detected"
    assert d.place_voice_call is False


def test_empty_history_is_neutral_no_op():
    d = decide_escalation([], None, escalation_level=0)
    assert d.event_type is None
    assert d.escalation_level == 0


def test_four_plus_misses_still_level_2():
    history = [_ci(i, False) for i in range(5)]
    d = decide_escalation(history, history[-1]["timestamp"], escalation_level=2)
    assert d.rung == "three_plus"
    assert d.escalation_level == 2


# --------------------------------------------------------------------------- #
# Node behaviour — LLM is consulted for text ONLY                             #
# --------------------------------------------------------------------------- #
class _FakeStructured:
    def __init__(self, value, recorder):
        self._value = value
        self._rec = recorder

    def invoke(self, messages):
        self._rec.append(messages)
        return self._value


class FakeLLM:
    """Records structured-output calls; returns a fixed message object."""

    def __init__(self, message="Warm note about your plan."):
        self._value = SimpleNamespace(message=message)
        self.invocations: list = []

    def with_structured_output(self, schema):
        return _FakeStructured(self._value, self.invocations)


def test_node_on_time_does_not_call_llm():
    llm = FakeLLM()
    agent = AccountabilityAgent(llm=llm)
    state = {
        "user_id": "u1",
        "active_goal": {"title": "Learn Spanish", "domain": "language"},
        "plan": [{"description": "20-min Spanish", "date": None}],
        "checkin_history": [_ci(0, True)],
        "last_checkin_at": BASE,
        "streak": 1,
        "escalation_level": 0,
    }
    updates = agent(state)

    assert llm.invocations == []  # no LLM for an on-time streak
    assert updates["escalation_level"] == 0
    assert updates["pending_event"]["type"] == "streak_maintained"
    assert "intervention_message" not in updates


def test_node_one_miss_generates_message_only():
    llm = FakeLLM(message="Looks like today's session got skipped — short version tonight?")
    agent = AccountabilityAgent(llm=llm)
    state = {
        "user_id": "u1",
        "active_goal": {"title": "Learn Spanish", "domain": "language"},
        "plan": [{"description": "20-min Spanish", "date": None}],
        "checkin_history": [_ci(0, True), _ci(1, False)],
        "last_checkin_at": BASE + timedelta(days=1),
        "streak": 0,
        "escalation_level": 0,
    }
    updates = agent(state)

    assert len(llm.invocations) == 1  # exactly one text generation
    assert updates["intervention_message"].startswith("Looks like")
    assert updates.get("pending_event") is None  # a miss never rewards the world
    assert updates["escalation_level"] == 0


def test_node_three_plus_misses_flags_voice_call():
    llm = FakeLLM(message="Hi — it's been a little while, no pressure at all...")
    agent = AccountabilityAgent(llm=llm)
    state = {
        "user_id": "u1",
        "active_goal": {"title": "Learn Spanish", "domain": "language"},
        "plan": [{"description": "20-min Spanish", "date": None}],
        "checkin_history": [_ci(0, False), _ci(1, False), _ci(2, False)],
        "last_checkin_at": BASE + timedelta(days=2),
        "streak": 0,
        "escalation_level": 1,
    }
    updates = agent(state)

    assert updates["escalation_level"] == 2
    assert updates["place_voice_call"] is True
    assert len(llm.invocations) == 1
