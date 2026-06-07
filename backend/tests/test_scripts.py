"""CI checks for the demo scripts (offline / dry-run paths only).

No real call, no Supabase, no Ollama. Confirms the seeder produces realistic data
and is idempotent, and that the rehearsal narrative runs end-to-end with a mocked
Vapi client (acceptance criteria for Task 3).
"""

from scripts import demo_rehearsal, seed_demo_user


def test_seed_creates_realistic_demo_data_and_is_idempotent():
    rel = seed_demo_user._DryRunRelational()
    uid = "demo"

    seed_demo_user.seed(rel, uid)
    state = rel.get_user_state(uid)

    # Goal + believable history + resilient comeback stone all present.
    assert "Spanish" in state["active_goal"]["title"]
    history = state["checkin_history"]
    assert len(history) >= 12
    assert any(not c["completed"] for c in history)  # has misses (Monday skips)
    variants = [s["variant"] for s in state["world_state"].stones]
    assert "resilient" in variants

    checkin_count = len(history)

    # Idempotent: a second run must not duplicate goal/check-ins.
    seed_demo_user.seed(rel, uid)
    assert len(rel.get_user_state(uid)["checkin_history"]) == checkin_count


def test_rehearsal_offline_runs_full_narrative_with_mocked_vapi():
    service, rel, vapi = demo_rehearsal.build_offline_service()
    demo_rehearsal.run(service, vapi, "demo-offline")

    # Escalation reached level 2 and a (mocked) call was placed.
    final = service.get_state("demo-offline")
    assert final["escalation_level"] == 2
    assert len(vapi.calls) >= 1
    # Variables passed to the call were built from live state (exact key contract).
    _, _, variables = vapi.calls[0]
    assert variables["goalName"].startswith("Learn Spanish")
