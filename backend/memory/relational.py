"""Relational memory backend (Supabase / Postgres).

Wraps the supabase-py client. Structured, queryable state lives here: users,
goals, milestones, check-ins, world-state snapshots and reflection notes.

The client is injectable so tests can pass a fake; the real ``supabase``
dependency (and ``config``) are imported lazily only when no client is supplied.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from state import (
    CheckIn,
    Goal,
    Milestone,
    Stone,
    UserState,
    WorldState,
    new_user_state,
)

if TYPE_CHECKING:  # keep supabase out of module import for light test runs
    from supabase import Client


def _to_iso(value: Any) -> Any:
    """Serialize datetime/date to ISO strings; pass everything else through."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class RelationalMemory:
    """Typed read/write access to the relational store."""

    def __init__(self, client: "Client | None" = None) -> None:
        if client is None:
            from config import get_settings  # lazy
            from supabase import create_client  # lazy

            settings = get_settings()
            client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
            )
        self.client = client

    # ----- check-ins ---------------------------------------------------- #
    def append_checkin(self, user_id: str, checkin: CheckIn) -> None:
        payload = {
            "user_id": user_id,
            "action_id": checkin.get("action_id"),
            "completed": checkin.get("completed", False),
            "note": checkin.get("note"),
            "timestamp": _to_iso(checkin.get("timestamp")),
        }
        self.client.table("checkins").insert(payload).execute()

    def get_checkin_history(self, user_id: str, limit: int = 50) -> list[CheckIn]:
        res = (
            self.client.table("checkins")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_checkin(row) for row in (res.data or [])]

    @staticmethod
    def _row_to_checkin(row: dict) -> CheckIn:
        return CheckIn(
            timestamp=_parse_dt(row.get("timestamp")),
            action_id=row.get("action_id"),
            completed=bool(row.get("completed", False)),
            note=row.get("note"),
        )

    # ----- users / goals / reflection writes (Task 3) ------------------ #
    def ensure_user(self, user_id: str, display_name: str | None = None) -> None:
        """Upsert a users row by explicit id (lets demo/seed use a stable id)."""
        payload: dict = {"id": user_id}
        if display_name is not None:
            payload["display_name"] = display_name
        self.client.table("users").upsert(payload).execute()

    def save_goal(self, user_id: str, goal: Goal) -> str | None:
        """Persist a goal (deactivating any prior active goal) and its milestones.

        Returns the new goal's id when the client echoes it (real Supabase does;
        fakes may not). Goals/milestones are owned here — ``save_user_state``
        deliberately does not touch them.
        """
        # Only one active goal at a time.
        self.client.table("goals").update({"is_active": False}).eq(
            "user_id", user_id
        ).eq("is_active", True).execute()

        res = (
            self.client.table("goals")
            .insert(
                {
                    "user_id": user_id,
                    "title": goal.get("title"),
                    "domain": goal.get("domain"),
                    "target_date": _to_iso(goal.get("target_date")),
                    "is_active": True,
                }
            )
            .execute()
        )
        rows = res.data or []
        goal_id = rows[0].get("id") if rows else None

        for m in goal.get("milestones") or []:
            self.client.table("milestones").insert(
                {
                    "goal_id": goal_id,
                    "description": m.get("description"),
                    "target_date": _to_iso(m.get("target_date")),
                    "completed": bool(m.get("completed", False)),
                }
            ).execute()
        return goal_id

    def add_reflection_note(
        self, user_id: str, note: str, domain: str | None = None
    ) -> None:
        """Insert one reflection note (relational mirror of the vector store)."""
        self.client.table("reflection_notes").insert(
            {"user_id": user_id, "note": note, "domain": domain}
        ).execute()

    # ----- full user state --------------------------------------------- #
    def get_user_state(self, user_id: str) -> UserState | None:
        res = (
            self.client.table("users")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]

        state = new_user_state(user_id)
        state["streak"] = int(row.get("streak", 0) or 0)
        state["escalation_level"] = int(row.get("escalation_level", 0) or 0)
        state["last_checkin_at"] = _parse_dt(row.get("last_checkin_at"))
        state["checkin_history"] = self.get_checkin_history(user_id)
        state["world_state"] = self._load_world_state(user_id)
        state["reflection_notes"] = self._load_reflection_notes(user_id)
        state["active_goal"] = self._load_active_goal(user_id)
        return state

    def save_user_state(self, user_id: str, state: UserState) -> None:
        """Persist scalar user fields and the world-state snapshot.

        Goals/milestones are owned by the Planner and check-ins by
        :meth:`append_checkin`; Task 1 deliberately syncs only the ``users`` row
        and the ``world_states`` snapshot here.
        """
        self.client.table("users").upsert(
            {
                "id": user_id,
                "streak": state.get("streak", 0),
                "escalation_level": state.get("escalation_level", 0),
                "last_checkin_at": _to_iso(state.get("last_checkin_at")),
            }
        ).execute()

        world = state.get("world_state") or WorldState()
        self.client.table("world_states").upsert(
            {
                "user_id": user_id,
                "balance_level": world.balance_level,
                "stones": [self._serialize_stone(s) for s in world.stones],
            }
        ).execute()

    # ----- loaders / serializers --------------------------------------- #
    def _load_world_state(self, user_id: str) -> WorldState:
        res = (
            self.client.table("world_states")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return WorldState()
        row = rows[0]
        stones = [self._deserialize_stone(s) for s in (row.get("stones") or [])]
        return WorldState(
            stones=stones,
            balance_level=int(row.get("balance_level", 0) or 0),
        )

    def _load_reflection_notes(self, user_id: str) -> list[str]:
        res = (
            self.client.table("reflection_notes")
            .select("note")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [row["note"] for row in (res.data or []) if row.get("note")]

    def _load_active_goal(self, user_id: str) -> Goal | None:
        res = (
            self.client.table("goals")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        g = rows[0]
        return Goal(
            title=g.get("title"),
            domain=g.get("domain"),
            target_date=_parse_date(g.get("target_date")),
            milestones=self._load_milestones(g.get("id")),
        )

    def _load_milestones(self, goal_id: Any) -> list[Milestone]:
        if goal_id is None:
            return []
        res = (
            self.client.table("milestones")
            .select("*")
            .eq("goal_id", goal_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [
            Milestone(
                description=row.get("description"),
                target_date=_parse_date(row.get("target_date")),
                completed=bool(row.get("completed", False)),
            )
            for row in (res.data or [])
        ]

    @staticmethod
    def _serialize_stone(stone: Stone) -> dict:
        return {
            "variant": stone.get("variant"),
            "created_at": _to_iso(stone.get("created_at")),
            "from_user_id": stone.get("from_user_id"),
        }

    @staticmethod
    def _deserialize_stone(raw: dict) -> Stone:
        return Stone(
            variant=raw.get("variant"),
            created_at=_parse_dt(raw.get("created_at")),
            from_user_id=raw.get("from_user_id"),
        )
