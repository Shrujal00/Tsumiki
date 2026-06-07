"""The Tsumiki Engine — deterministic world-state mutation (agents.md §7).

Plain rules-based code. **No LLM calls, no external dependencies.** Consumes a
single ``AgentEvent`` and returns the (mutated) ``WorldState``. Because it is pure
and deterministic it behaves identically on every run — exactly what you want
running live in front of judges, and what makes it trivially unit-testable.

Faithfulness note: ``apply_event`` implements the four event-type branches given
verbatim in agents.md §7 (``milestone_reached``, ``streak_maintained``,
``setback_recovered``, ``support_received``). The fifth declared ``EventType``,
``comeback_detected``, has *no* branch in §7 — by design. A comeback is handled by
the Accountability Agent (it resets ``escalation_level`` to 0 and is acknowledged
warmly in messaging); it deliberately does not mint a stone here. So an event of
type ``comeback_detected`` is a documented no-op: the world_state is returned
unchanged. This keeps the engine an exact transcription of the spec while still
accepting every value of the ``EventType`` literal.
"""

from __future__ import annotations

from state import AgentEvent, Difficulty, StoneVariant, WorldState


def stone_variant_for(difficulty: Difficulty) -> StoneVariant:
    """Map an achievement ``difficulty`` to the stone ``variant`` it earns.

    ``small`` / ``medium`` / ``large`` are valid stone variants in their own
    right, so this is an identity mapping today — but it is kept as an explicit,
    named function so the difficulty→variant policy lives in exactly one place and
    can grow (e.g. special variants for milestones) without touching callers.
    """
    mapping: dict[Difficulty, StoneVariant] = {
        "small": "small",
        "medium": "medium",
        "large": "large",
    }
    return mapping[difficulty]


def apply_event(world_state: WorldState, event: AgentEvent) -> WorldState:
    """Apply one ``AgentEvent`` to ``world_state`` and return it.

    Mutates ``world_state`` in place (via its ``add_stone`` / ``reinforce_balance``
    methods) and returns the same object for convenient chaining. Implements
    agents.md §7 exactly; unknown / no-effect event types (``comeback_detected``)
    leave the world unchanged.
    """
    if event["type"] == "milestone_reached":
        world_state.add_stone(variant=stone_variant_for(event["difficulty"]))
    elif event["type"] == "streak_maintained":
        world_state.reinforce_balance()
    elif event["type"] == "setback_recovered":
        world_state.add_stone(variant="resilient")  # marks comebacks positively
    elif event["type"] == "support_received":
        world_state.add_stone(variant="gifted", from_user=event.get("from_user_id"))
    return world_state
