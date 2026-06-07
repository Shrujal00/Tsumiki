"""Idempotent demo-data seeder.

Creates ONE realistic demo user so the live demo never starts from an empty
visual:

* goal: "Learn Spanish — 20 min/day, 3x/week"
* a believable check-in history: mostly on-time, a clear *skips-Mondays* pattern
  (so the Reflection Agent has a real signal to find), and a missed-streak →
  comeback sequence
* a partially-built world_state (a few stones already present, including at least
  one ``resilient`` comeback stone)

Run from the backend directory::

    python scripts/seed_demo_user.py            # writes to Supabase
    python scripts/seed_demo_user.py --dry-run  # build + print only, no DB

Re-running is safe: existing data is detected and left alone (logged as "found").
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:  # em-dash in the demo goal title needs UTF-8 on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from state import CheckIn, Goal, Stone, WorldState  # noqa: E402

# Stable demo user id so the dashboard/app always point at the same record.
DEFAULT_DEMO_USER_ID = "11111111-1111-1111-1111-111111111111"

# Anchor the synthetic history to a fixed "today" for reproducibility.
TODAY = date(2026, 6, 8)  # a Monday
_WEEKDAY = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def demo_goal() -> Goal:
    return {
        "title": "Learn Spanish — 20 min/day, 3x/week",
        "domain": "language",
        "target_date": date(2026, 9, 1),
        "milestones": [
            {"description": "Finish A1 basics", "target_date": date(2026, 7, 1), "completed": False},
            {"description": "Hold a 5-minute conversation", "target_date": date(2026, 8, 1), "completed": False},
        ],
    }


def _at(d: date, hour: int = 8) -> datetime:
    return datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)


def demo_checkins() -> list[CheckIn]:
    """6 weeks of Mon/Wed/Fri sessions with a clear Monday-skip pattern.

    Plus, three weeks back, a Wed+Fri miss (a missed streak) followed by a
    completed comeback the next Monday-after — material for the escalation and
    comeback narratives.
    """
    checkins: list[CheckIn] = []
    start = TODAY - timedelta(weeks=6)
    # advance to the first Monday on/after start
    start += timedelta(days=(7 - start.weekday()) % 7)

    for week in range(6):
        monday = start + timedelta(weeks=week)
        for day_name in ("Mon", "Wed", "Fri"):
            d = monday + timedelta(days=_WEEKDAY[day_name] - _WEEKDAY["Mon"])
            if d >= TODAY:
                continue
            # Mondays: the user reliably skips them.
            completed = day_name != "Mon"
            note = None
            # Week 3: a missed streak (Wed+Fri missed too) then a comeback.
            if week == 3 and day_name in ("Wed", "Fri"):
                completed = False
            if week == 4 and day_name == "Wed":
                completed = True
                note = "Back at it after a rough week."
            checkins.append(
                CheckIn(
                    timestamp=_at(d),
                    action_id=f"plan-{d.isoformat()}",
                    completed=completed,
                    note=note,
                )
            )
    return checkins


def demo_world_state() -> WorldState:
    """A few earned stones already, including a resilient comeback stone."""
    ws = WorldState(balance_level=3)
    base = _at(TODAY - timedelta(weeks=6))
    seeded: list[Stone] = [
        {"variant": "small", "created_at": base, "from_user_id": None},
        {"variant": "medium", "created_at": base + timedelta(weeks=1), "from_user_id": None},
        {"variant": "small", "created_at": base + timedelta(weeks=2), "from_user_id": None},
        # The comeback after the week-3 missed streak:
        {"variant": "resilient", "created_at": base + timedelta(weeks=4), "from_user_id": None},
    ]
    ws.stones = seeded
    return ws


# --------------------------------------------------------------------------- #
# Writer                                                                      #
# --------------------------------------------------------------------------- #
def seed(relational, user_id: str) -> None:
    existing = relational.get_user_state(user_id)

    relational.ensure_user(user_id, display_name="Demo User")

    if existing and existing.get("active_goal"):
        print(f"  found existing goal for {user_id} — leaving it as is")
    else:
        relational.save_goal(user_id, demo_goal())
        print("  created goal: Learn Spanish — 20 min/day, 3x/week")

    if existing and existing.get("checkin_history"):
        print(f"  found {len(existing['checkin_history'])} existing check-ins — skipping")
    else:
        checkins = demo_checkins()
        for ci in checkins:
            relational.append_checkin(user_id, ci)
        misses = sum(1 for c in checkins if not c["completed"])
        print(f"  inserted {len(checkins)} check-ins ({misses} misses, incl. Monday skips)")

    if existing and (existing.get("world_state") and existing["world_state"].stones):
        print("  found existing world_state — leaving it as is")
    else:
        ws = demo_world_state()
        state = existing or {"user_id": user_id}
        state["world_state"] = ws
        state.setdefault("streak", 2)
        state.setdefault("escalation_level", 0)
        state.setdefault("last_checkin_at", _at(TODAY - timedelta(days=3)))
        relational.save_user_state(user_id, state)  # writes world_states snapshot
        variants = ", ".join(s["variant"] for s in ws.stones)
        print(f"  seeded world_state: balance={ws.balance_level}, stones=[{variants}]")


# --------------------------------------------------------------------------- #
# Dry-run fake (no DB) — lets the script be validated offline                  #
# --------------------------------------------------------------------------- #
class _DryRunRelational:
    def __init__(self):
        self.store: dict = {}

    def get_user_state(self, user_id):
        return self.store.get(user_id)

    def ensure_user(self, user_id, display_name=None):
        self.store.setdefault(user_id, {"user_id": user_id, "checkin_history": []})

    def save_goal(self, user_id, goal):
        self.store[user_id]["active_goal"] = goal
        return "dry-goal"

    def append_checkin(self, user_id, checkin):
        self.store[user_id].setdefault("checkin_history", []).append(checkin)

    def add_reflection_note(self, user_id, note, domain=None):
        pass

    def save_user_state(self, user_id, state):
        # Mirror real RelationalMemory: update world + scalars, never wipe the
        # goal/check-ins written by save_goal/append_checkin.
        cur = self.store.setdefault(user_id, {"user_id": user_id, "checkin_history": []})
        if state.get("world_state") is not None:
            cur["world_state"] = state["world_state"]
        for k in ("streak", "escalation_level", "last_checkin_at"):
            if k in state:
                cur[k] = state[k]
        if state.get("active_goal"):
            cur["active_goal"] = state["active_goal"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Tsumiki demo user")
    parser.add_argument("--dry-run", action="store_true", help="build + print, no DB writes")
    args = parser.parse_args()

    user_id = DEFAULT_DEMO_USER_ID
    if args.dry_run:
        print("[dry-run] no database writes will occur")
        relational = _DryRunRelational()
    else:
        from config import get_settings
        from memory.relational import RelationalMemory

        user_id = get_settings().DEMO_USER_ID or DEFAULT_DEMO_USER_ID
        relational = RelationalMemory()

    print(f"Seeding demo user {user_id} ...")
    seed(relational, user_id)
    print("Done. Demo user is ready.")
    print(f"DEMO_USER_ID={user_id}")


if __name__ == "__main__":
    main()
