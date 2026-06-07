"""Demo rehearsal — runs the whole live-demo narrative end to end.

This is the team's safety net: if this runs clean, the live demo will too. The
Vapi client is ALWAYS mocked here — this script never places a real call.

Modes::

    python scripts/demo_rehearsal.py            # real agents/Supabase, mocked Vapi
    python scripts/demo_rehearsal.py --offline  # fully self-contained, no Ollama/DB

The ``--offline`` mode wires fake LLMs + an in-memory store so the narrative can
be rehearsed (and CI-checked) with zero external dependencies. The deterministic
parts (escalation ladder, Tsumiki Engine) run for real in both modes.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:  # ensure non-ASCII (arrows, em-dashes) print on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from integrations.vapi import CallResult  # noqa: E402
from service import TsumikiService  # noqa: E402
from state import UserState, WorldState, new_user_state  # noqa: E402

NOW = datetime(2026, 6, 8, 9, 0, 0, tzinfo=timezone.utc)
DEMO_USER = "11111111-1111-1111-1111-111111111111"


def hr(title: str) -> None:
    print("\n" + "=" * 68)
    print(f"  {title}")
    print("=" * 68)


def world_summary(ws: WorldState | None) -> str:
    ws = ws or WorldState()
    variants = [s["variant"] for s in ws.stones]
    return f"balance={ws.balance_level}, stones={variants}"


# --------------------------------------------------------------------------- #
# Always-mocked Vapi                                                          #
# --------------------------------------------------------------------------- #
class MockVapi:
    def __init__(self):
        self.calls = []

    def place_escalation_call(self, user_id, phone_number, variables):
        self.calls.append((user_id, phone_number, variables))
        print(f"    [MOCK Vapi] would call {phone_number} with variables:")
        for k, v in variables.items():
            print(f"      {k} = {v}")
        # Simulate a terminal outcome for the closed feedback loop.
        return CallResult(
            id="mock-call-1",
            status="answered",
            user_response_summary="User said they'll do a short session tonight.",
        )


# --------------------------------------------------------------------------- #
# Offline fakes                                                               #
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
    def query_similar(self, user_id, query_text, k=5):
        return []

    def add_reflection(self, user_id, text, metadata):
        pass


class FakeRelational:
    """Mirrors real RelationalMemory semantics: check-in history is written ONLY
    via append_checkin (row store); save_user_state persists scalars + world, not
    history; get_user_state returns a fresh copy each call (rebuilt-from-DB-like).
    """

    def __init__(self):
        self.states: dict = {}

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
        return "goal-1"

    def append_checkin(self, user_id, checkin):
        self.ensure_user(user_id)
        self.states[user_id]["checkin_history"].append(checkin)

    def add_reflection_note(self, user_id, note, domain=None):
        pass

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
        # NOTE: deliberately does not persist checkin_history.


def build_offline_service():
    from agents.accountability import AccountabilityAgent
    from agents.game_master import GameMasterAgent
    from agents.planner import PlannerAgent
    from agents.reflection import ReflectionAgent

    plan_value = SimpleNamespace(
        milestones=[SimpleNamespace(description="Finish A1 basics", target_date=date(2026, 7, 1))],
        actions=[
            SimpleNamespace(date=date(2026, 6, 9), description="Learn 10 greetings", estimated_effort="15 min", milestone_index=0),
            SimpleNamespace(date=date(2026, 6, 11), description="Practice numbers 1-20", estimated_effort="15 min", milestone_index=0),
        ],
    )
    rel = FakeRelational()
    vapi = MockVapi()
    service = TsumikiService(
        relational=rel,
        vapi=vapi,
        planner=PlannerAgent(llm=FakeLLM(plan_value)),
        accountability=AccountabilityAgent(llm=FakeLLM(SimpleNamespace(message="No worries at all — want to do a short 5-minute version tonight?"))),
        game_master=GameMasterAgent(),
        reflection=ReflectionAgent(
            llm=FakeLLM(SimpleNamespace(insights=["~80% of missed sessions fall on Mondays — likely a recurring scheduling conflict"])),
            vector=FakeVector(),
        ),
    )
    return service, rel, vapi


def build_real_service():
    from memory.relational import RelationalMemory

    vapi = MockVapi()  # never real, even in "real" mode
    service = TsumikiService(relational=RelationalMemory(), vapi=vapi)
    return service, service.relational, vapi


# --------------------------------------------------------------------------- #
# Narrative                                                                   #
# --------------------------------------------------------------------------- #
def run(service: TsumikiService, vapi: MockVapi, user_id: str) -> None:
    goal = {
        "title": "Learn Spanish — 20 min/day, 3x/week",
        "domain": "language",
        "target_date": date(2026, 9, 1),
        "milestones": [
            {"description": "Finish A1 basics", "target_date": date(2026, 7, 1), "completed": False},
        ],
    }

    hr("STEP 1 — Create goal → generated plan")
    state = service.create_goal(user_id, goal)
    print(f"  goal: {goal['title']}")
    for a in state.get("plan") or []:
        print(f"    • {a.get('date')}  {a['description']}  ({a.get('estimated_effort')})")

    world_before_str = world_summary(_current_world(service, user_id, state))
    print(f"\n  world BEFORE: {world_before_str}")

    hr("STEP 2 — Successful check-in → world_state grows")
    out = service.record_checkin(
        user_id,
        {"timestamp": NOW, "action_id": "plan-1", "completed": True, "note": "done"},
    )
    print(f"  world AFTER check-in: {world_summary(out['state'].get('world_state'))}")
    print(f"  escalation_level: {out['state'].get('escalation_level')}")

    hr("STEP 3 — Simulated missed check-ins → escalation rises")
    for i in range(1, 4):
        miss = {
            "timestamp": NOW + timedelta(days=i),
            "action_id": f"plan-miss-{i}",
            "completed": False,
            "note": None,
        }
        out = service.record_checkin(user_id, miss, phone_number="+15555550123", user_name="Demo User")
        lvl = out["state"].get("escalation_level")
        print(f"  miss #{i} → escalation_level = {lvl}")

    hr("STEP 4 — Escalation call (MOCKED Vapi — never a real call)")
    if out["call_result"]:
        cr = out["call_result"]
        print(f"  call status: {cr.status}")
        print(f"  user response logged: {cr.user_response_summary}")
    else:
        print("  (no call placed — check phone_number / escalation level)")
    print(f"  total mock calls placed: {len(vapi.calls)}")

    hr("STEP 5 — Reflection → new reflection_notes")
    reflected = service.run_reflection(user_id)
    for note in reflected.get("reflection_notes") or []:
        print(f"    • {note}")

    hr("STEP 6 — Before / after world_state diff")
    world_after = _current_world(service, user_id, reflected)
    print(f"  BEFORE: {world_before_str}")
    print(f"  AFTER : {world_summary(world_after)}")

    print("\nRehearsal complete — narrative ran clean. ✅")


def _current_world(service: TsumikiService, user_id: str, fallback: UserState) -> WorldState:
    try:
        return service.get_state(user_id).get("world_state")
    except Exception:
        return fallback.get("world_state")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rehearse the Tsumiki demo")
    parser.add_argument("--offline", action="store_true", help="no Ollama/Supabase; fakes")
    args = parser.parse_args()

    if args.offline:
        print("[offline] fake LLMs + in-memory store; deterministic parts run for real")
        service, _, vapi = build_offline_service()
        user_id = "demo-offline"
    else:
        from config import get_settings

        service, _, vapi = build_real_service()
        user_id = get_settings().DEMO_USER_ID or DEMO_USER

    run(service, vapi, user_id)


if __name__ == "__main__":
    main()
