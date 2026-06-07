"""Unit tests for the Vapi client — NO real calls.

The HTTP layer is faked; we assert the request shape (endpoint, auth header,
exact assistantOverrides.variableValues keys) and the variable-building logic.
The private key is never asserted into logs anywhere.
"""

from datetime import datetime, timedelta, timezone

import pytest

from integrations.vapi import (
    REQUIRED_VARIABLE_KEYS,
    VapiClient,
    build_call_variables,
)

NOW = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeHttp:
    def __init__(self, data):
        self._data = data
        self.posts = []

    def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse(self._data)


def _client(http):
    return VapiClient(
        api_key="secret-key",
        assistant_id="asst-1",
        phone_number_id="pn-1",
        http=http,
    )


def test_build_call_variables_has_exactly_required_keys():
    state = {
        "active_goal": {"title": "Learn Spanish"},
        "plan": [{"description": "20-min Spanish"}],
        "streak": 4,
        "last_checkin_at": NOW - timedelta(days=2),
    }
    variables = build_call_variables(state, user_name="Asha", now=NOW)

    assert set(variables) == REQUIRED_VARIABLE_KEYS
    assert variables["userName"] == "Asha"
    assert variables["goalName"] == "Learn Spanish"
    assert variables["todayPlannedAction"] == "20-min Spanish"
    assert variables["currentStreakDays"] == "4"
    assert variables["daysSinceLastCheckin"] == "2"
    assert variables["lastCheckinDate"] == "2026-06-06"
    assert all(isinstance(v, str) for v in variables.values())


def test_place_call_posts_correct_payload():
    http = FakeHttp({"id": "call-9", "status": "queued"})
    client = _client(http)
    variables = build_call_variables(
        {"active_goal": {"title": "G"}, "plan": [], "streak": 0, "last_checkin_at": NOW},
        now=NOW,
    )

    result = client.place_escalation_call("u1", "+15555550123", variables)

    assert result.id == "call-9"
    assert result.status == "queued"
    post = http.posts[0]
    assert post["url"].endswith("/call")
    assert post["headers"]["Authorization"] == "Bearer secret-key"
    body = post["json"]
    assert body["assistantId"] == "asst-1"
    assert body["phoneNumberId"] == "pn-1"
    assert body["customer"]["number"] == "+15555550123"
    assert set(body["assistantOverrides"]["variableValues"]) == REQUIRED_VARIABLE_KEYS


def test_place_call_rejects_wrong_variable_keys():
    client = _client(FakeHttp({}))
    with pytest.raises(ValueError):
        client.place_escalation_call("u1", "+1555", {"userName": "x"})  # missing keys


def test_place_call_requires_phone_number_id():
    client = VapiClient(api_key="k", assistant_id="a", phone_number_id=None, http=FakeHttp({}))
    variables = build_call_variables(
        {"active_goal": {}, "plan": [], "streak": 0, "last_checkin_at": NOW}, now=NOW
    )
    with pytest.raises(RuntimeError):
        client.place_escalation_call("u1", "+1555", variables)
