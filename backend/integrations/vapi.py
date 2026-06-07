"""Vapi voice-escalation client (agents.md §5, Features.md §5).

A thin, server-side-only wrapper over Vapi's REST API. Tsumiki supplies the
escalation decision and the personalized variable values; Vapi supplies the
channel (telephony via Twilio + STT/TTS) and runs the pre-built assistant.

Security: this uses the Vapi **private** key (``VAPI_API_KEY``). It is read from
config, sent only in the ``Authorization`` header, and never logged, returned, or
echoed. Construct one server-side; never expose it to a client.

Test policy: NEVER place a real call from automated tests or the rehearsal script
— inject a fake/mocked ``VapiClient`` there. Only ``scripts/test_call.py`` (run by
a human) places a real call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

VAPI_BASE_URL = "https://api.vapi.ai"

# EXACTLY the template variables the configured Vapi assistant expects. The call
# payload must carry these keys and only these keys.
REQUIRED_VARIABLE_KEYS = frozenset(
    {
        "userName",
        "goalName",
        "todayPlannedAction",
        "currentStreakDays",
        "daysSinceLastCheckin",
        "lastCheckinDate",
    }
)


@dataclass
class CallResult:
    """Outcome of a placed call.

    A freshly placed call is ``queued``; the terminal outcome (``answered`` /
    ``voicemail``) and a ``user_response_summary`` arrive asynchronously from
    Vapi's end-of-call report (logged back via the closed feedback loop). In a
    mocked test/rehearsal these terminal fields are set directly.
    """

    id: Optional[str]
    status: str
    user_response_summary: Optional[str] = None
    raw: Optional[dict] = None

    @property
    def answered(self) -> bool:
        return self.status == "answered"

    @property
    def voicemail(self) -> bool:
        return self.status == "voicemail"


def build_call_variables(
    state: dict,
    user_name: str | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    """Build the assistant's ``variableValues`` live from the current UserState.

    Every value is stringified (Vapi template variables are strings). Values are
    pulled from state — never hardcoded — so the call references the user's real
    goal, plan item and streak.
    """
    now = now or datetime.now(timezone.utc)
    goal = state.get("active_goal") or {}
    plan = state.get("plan") or []
    last = state.get("last_checkin_at")

    if isinstance(last, datetime):
        days_since = max((now - last).days, 0)
        last_date = last.date().isoformat()
    else:
        days_since = 0
        last_date = "never"

    return {
        "userName": user_name or "there",
        "goalName": str(goal.get("title") or "your goal"),
        "todayPlannedAction": str(
            plan[0]["description"] if plan else "your next session"
        ),
        "currentStreakDays": str(state.get("streak", 0)),
        "daysSinceLastCheckin": str(days_since),
        "lastCheckinDate": last_date,
    }


class VapiClient:
    """Server-side Vapi REST client. Holds the private key; never exposes it."""

    def __init__(
        self,
        api_key: str | None = None,
        assistant_id: str | None = None,
        phone_number_id: str | None = None,
        http: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._assistant_id = assistant_id
        self._phone_number_id = phone_number_id
        self._http = http  # inject an httpx.Client-like object in tests

    # ----- lazy config ------------------------------------------------- #
    def _load_config(self) -> None:
        if self._api_key and self._assistant_id is not None:
            return
        from config import get_settings  # lazy

        settings = get_settings()
        if self._api_key is None:
            self._api_key = settings.VAPI_API_KEY.get_secret_value()
        if self._assistant_id is None:
            self._assistant_id = settings.VAPI_ASSISTANT_ID
        if self._phone_number_id is None:
            self._phone_number_id = settings.VAPI_PHONE_NUMBER_ID

    @property
    def http(self) -> Any:
        if self._http is None:
            import httpx  # lazy

            self._http = httpx.Client(timeout=30.0)
        return self._http

    # ----- public API -------------------------------------------------- #
    def place_escalation_call(
        self,
        user_id: str,
        phone_number: str,
        variables: dict,
    ) -> CallResult:
        """Place one outbound escalation call. Raises on misconfig / bad vars.

        ``variables`` must contain EXACTLY ``REQUIRED_VARIABLE_KEYS``.
        """
        keys = set(variables)
        if keys != REQUIRED_VARIABLE_KEYS:
            missing = REQUIRED_VARIABLE_KEYS - keys
            extra = keys - REQUIRED_VARIABLE_KEYS
            raise ValueError(
                f"variableValues key mismatch — missing={sorted(missing)} "
                f"extra={sorted(extra)}"
            )

        self._load_config()
        if not self._phone_number_id:
            raise RuntimeError(
                "VAPI_PHONE_NUMBER_ID is not set; cannot place an outbound call. "
                "Set it in .env.local (the Vapi-owned caller-ID)."
            )

        payload = {
            "assistantId": self._assistant_id,
            "phoneNumberId": self._phone_number_id,
            "customer": {"number": phone_number},
            "assistantOverrides": {"variableValues": variables},
        }
        resp = self.http.post(
            f"{VAPI_BASE_URL}/call",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return CallResult(
            id=data.get("id"),
            status=data.get("status", "queued"),
            raw=data,
        )
