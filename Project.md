# Niwa (庭) — Tend Your Goals Like a Garden

**FAR AWAY 2026 — Theme: Agentic & Autonomous Systems**

---

## 1. Problem Statement

People increasingly turn to ChatGPT, Claude, and similar tools as informal life coaches — for fitness goals, learning new skills, building habits, or working toward bigger personal ambitions. But this approach has three real, persistent problems:

- **Vague, generic responses.** A single general-purpose chatbot gives the same kind of advice to everyone, because it has no structured, persistent understanding of *this* person's specific goal, history, or patterns.
- **Context loss.** Every long conversation eventually runs into context-window limits. The assistant "forgets" what you told it three days ago, forcing you to re-explain yourself — which is exhausting and breaks the coaching relationship.
- **Cost and friction.** Long-running, high-context conversations are expensive to sustain, and there's no game-like structure that makes coming back every day feel rewarding rather than like a chore.

Meanwhile, gamified habit apps (Habitica, LifeUp) make progress feel like a game but have no real intelligence behind them — they're glorified checklists with XP bars. AI coaching apps (Rocky.ai, Purpose) add intelligence but are single chatbots wearing a "coach" persona — they have the same vagueness and memory problems as ChatGPT, just rebranded.

**Nobody has combined real multi-agent intelligence, structured persistent memory, and meaningful gamification into one system — wrapped in a calm, intentional design language instead of dopamine-loop pressure.**

---

## 2. The Solution: Niwa

Niwa is a **multi-agent goal-coaching system** themed around a Japanese garden. Instead of chatting with one generic AI, users work with a small team of specialized agents — each responsible for a different part of the coaching relationship — while their real-world progress is visualized as a garden that grows, season by season, as they grow.

Niwa is **domain-agnostic**: it works whether your goal is learning Spanish, training for a marathon, writing a novel, or building a daily meditation habit. The system plans the path, watches how you're actually doing, adapts when life gets in the way, and turns your real progress into a living, visible world — calmly, without guilt-tripping streak mechanics.

### Why this is different (validated gap)
We researched the existing landscape before committing to this idea:
- **Habitica / LifeUp** — strong gamification, no real coaching intelligence (just checklists with game skins).
- **Rocky.ai / Purpose** — AI coaching, but single-chatbot wrappers with the same vagueness/memory problems as ChatGPT.
- **Tea AI / Luvu** — gamified AI companions, but fitness-only, not general-purpose goals.
- **Duolingo** — remains language-only; has not expanded into general life-goal gamification.

No competitor combines (a) genuine multi-agent architecture with persistent structured memory, (b) domain-agnostic goal coaching, and (c) a calm/zen visual metaphor instead of a loud RPG or generic SaaS look. That combination is Niwa's gap to fill.

---

## 3. Multi-Agent Architecture

Niwa is built as an explicit **state graph** (via LangGraph), where each agent is a node that reads and writes a shared, typed state object — not a single model being re-prompted with different personalities. This is the core engineering differentiator: a visible, inspectable system of agents handing off structured work, not a chatbot in a costume.

| Agent | Role |
|---|---|
| **Planner Agent** | Breaks a high-level goal ("learn Spanish," "run a marathon") into a structured, time-boxed plan of milestones and daily/weekly actions. |
| **Accountability Agent** | Monitors check-ins against the plan, detects when the user is falling behind, and decides how to respond — a gentle nudge, a plan adjustment, or (if needed) escalation to a phone call. |
| **Reflection Agent** | Periodically reviews the user's check-in history and notes (via the memory store) to surface patterns — "you tend to skip Mondays," "you do best with morning sessions" — and feeds these insights back to the Planner. |
| **Game Master Agent** | Translates real progress into garden growth: emits structured events (milestone reached, streak maintained, setback recovered) that drive the visual world — without itself controlling the visuals directly (see Gamification Engine, below). |

Agents communicate only through the shared state object and the memory store — never through raw chat history — which is what keeps responses grounded and specific instead of generic.

---

## 4. Memory System (the core differentiator vs. ChatGPT/Claude)

Instead of relying on a sliding chat-history window (costly, lossy, and the direct cause of "vague" responses), Niwa gives each user a **hybrid structured memory**:

- **Relational store** (SQLite/Postgres): typed records for goals, milestones, check-in history, current plan state, and "world state" (garden stage, streaks, XP).
- **Vector store** (Chroma): semantic recall of qualitative reflections — "felt unmotivated on day 3," "enjoyed the evening session more than morning" — so agents can recall *relevant* context without re-reading entire conversation logs.

Each agent queries only the slice of memory relevant to its job. The Planner reads goal/milestone records; the Reflection Agent queries the vector store for patterns; the Accountability Agent reads recent check-in history. This is what allows Niwa to remember a goal from three days — or three weeks — ago accurately, cheaply, and specifically, instead of forgetting it or burning tokens re-reading everything each time.

---

## 5. Gamification Engine (deterministic, not LLM-driven)

A critical design decision: **the garden's growth, XP, and rewards are NOT decided by the LLM.** Agents emit structured JSON events (e.g., `{type: "milestone_reached", goal_id: ..., difficulty: ...}`), and a separate **rules-based engine** — plain code — converts those events into garden changes: a tree grows, a koi pond fills, a stone lantern lights up, the season shifts.

This matters for two reasons:
1. **Reliability** — game state can't be "hallucinated" or behave unpredictably during a live demo.
2. **Engineering judgment** — it shows a clear understanding of which decisions should be made by an LLM (planning, tone, adaptation) and which need deterministic guarantees (rewards, progress state) — exactly the kind of system-design thinking the judging rubric rewards under "Engineering Quality."

---

## 6. Voice Escalation: When a Notification Isn't Enough

Most habit apps stop at push notifications — easy to ignore, easy to silence. Niwa's Accountability Agent can make a genuinely autonomous decision: if a user misses check-ins repeatedly, the agent **escalates from a notification to an actual phone call**, generating a personalized script live from the user's real memory state ("Hey — it's day 4 of your guitar goal, you were on a 3-day streak, want to keep it going tonight?").

**Implementation: Vapi** (a voice-AI agent platform built specifically for "give my agent a phone number"), rather than standing up a full agent framework like OpenClaw or Hermes. Vapi wraps the telephony layer (via Twilio) and handles speech-to-text/text-to-speech, while Niwa's own multi-agent system remains the "brain" generating the call's content from structured memory. This keeps the build scoped and reliable within the timeline while still demonstrating genuine autonomous decision-making — the agent *deciding* to escalate, not a hardcoded reminder.

*(Demo safeguard: pre-test the call flow thoroughly and keep a recorded backup clip, since live telephony carries inherent demo risk.)*

---

## 7. Design Language: Zen, Not Dopamine Loops

Where Habitica and LifeUp lean into loud retro-RPG aesthetics, and Rocky/Purpose look like generic SaaS dashboards, Niwa takes a **Japanese garden** as its visual and emotional metaphor:
- Calm color palettes, slow and intentional animations, seasonal change over time
- Progress represented as organic growth (trees, ponds, stone paths) rather than bars, badges, or guilt-inducing streak counters
- The feeling of *tending* something living, rather than *grinding* for rewards

This is a genuine differentiation point in a market currently split between "gamer aesthetic" and "corporate wellness app" — and ties directly into the "Design & User Experience" judging criterion.

---

## 8. Tech Stack

- **Agent orchestration:** LangGraph (explicit state graph, typed shared state)
- **LLM layer:** Claude / GPT via API (model-agnostic where possible)
- **Structured memory:** SQLite or Postgres (relational) + Chroma (vector store for semantic recall)
- **Gamification engine:** custom rules-based service (deterministic, consumes structured agent events)
- **Voice escalation:** Vapi (voice AI agent platform, Twilio-backed telephony)
- **Frontend:** React-based web app with the garden visualization as the centerpiece
- **Backend:** Python (FastAPI) orchestrating agents, memory, and the gamification engine

---

## 9. Why This Fits FAR AWAY's Judging Criteria

- **Innovation & Technical Depth:** genuine multi-agent state-graph architecture + hybrid memory system, not a single-model wrapper
- **Engineering Quality:** clear separation of concerns — LLM agents for judgment, deterministic engine for reliability
- **Real-World Impact:** addresses a widespread, relatable problem (vague, forgetful AI coaching) with a concrete, demonstrable improvement
- **Scalability:** domain-agnostic design — works for any goal type without redesign
- **Design & User Experience:** distinctive zen aesthetic, calm interaction model, clear differentiation from existing gamified apps
- **Execution & Completeness:** demoable end-to-end loop — plan → check-in → memory update → adaptation → garden growth → (optional) voice escalation — all visible live

---

## 10. Live Demo Narrative

> "Watch the Planner Agent read this user's goal history from the memory store and generate this week's plan. Now watch the Accountability Agent detect a missed check-in — see it query the structured memory, decide to escalate, and generate a personalized message. Watch the Game Master Agent emit a structured event, and see the garden respond — live, on screen, backed by a real database update you can inspect."

This narrative directly proves the three things that separate Niwa from a "minimal-effort AI wrapper": visible agent hand-offs, persistent structured memory in action, and a deterministic system translating intelligence into a tangible, reliable result.
