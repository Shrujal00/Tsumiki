"""Manual real-call tester — HUMAN-RUN ONLY.

This is the ONLY place a real Vapi call is placed. Never invoke it from tests, CI,
or the rehearsal script. It dials a real number using the configured assistant and
realistic sample variables so you can confirm the assistant references the dynamic
values and matches the "warm, never shaming" tone before judging.

Usage (from the backend directory)::

    python scripts/test_call.py --phone +15555550123
    # or rely on DEMO_PHONE_NUMBER in .env.local:
    python scripts/test_call.py

Requires VAPI_API_KEY, VAPI_ASSISTANT_ID and VAPI_PHONE_NUMBER_ID in .env.local.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Realistic sample values matching the assistant's six template variables.
SAMPLE_VARIABLES = {
    "userName": "Asha",
    "goalName": "Learn Spanish — 20 min/day, 3x/week",
    "todayPlannedAction": "a 20-minute Spanish session",
    "currentStreakDays": "12",
    "daysSinceLastCheckin": "3",
    "lastCheckinDate": "2026-06-05",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Place ONE real Vapi escalation call")
    parser.add_argument("--phone", help="E.164 number to call, e.g. +15555550123")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    from config import get_settings
    from integrations.vapi import VapiClient

    settings = get_settings()
    phone = args.phone or settings.DEMO_PHONE_NUMBER
    if not phone:
        print("ERROR: no phone number. Pass --phone or set DEMO_PHONE_NUMBER.")
        sys.exit(1)

    print("About to place a REAL phone call via Vapi.")
    print(f"  to: {phone}")
    print("  variables:")
    for k, v in SAMPLE_VARIABLES.items():
        print(f"    {k} = {v}")

    if not args.yes:
        confirm = input("\nProceed with the real call? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    client = VapiClient()
    result = client.place_escalation_call("manual-test", phone, SAMPLE_VARIABLES)
    print(f"\nCall placed. id={result.id} status={result.status}")
    print("Listen for: warm tone, correct name/goal/streak, never shaming.")


if __name__ == "__main__":
    main()
