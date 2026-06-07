# Tsumiki — Full Feature Specification

**Team Pixex | FAR AWAY 2026 — Agentic & Autonomous Systems**

This document is the in-depth, end-to-end feature list for Tsumiki: every user-facing capability, every agent behavior, and every supporting system — organized by area so the team can divide work cleanly and judges can see full scope at a glance.

---

## 1. Onboarding & Goal Setup

- **Goal creation flow:** user states a goal in natural language ("learn Spanish," "run a 10K," "write a novel," "build a meditation habit") — fully domain-agnostic, no preset categories required.
- **Guided goal refinement:** the Planner Agent asks 2–3 clarifying questions if a goal is too vague ("by when?" "how many days a week can you commit?") and converts the answer into a structured goal record.
- **Initial plan generation:** Planner Agent produces a first milestone roadmap and a concrete first-week action plan, shown to the user for confirmation/adjustment before it's locked in.
- **Tone & pacing preferences:** lightweight setup questions (e.g., "do you want gentle reminders or more direct ones?") stored in user profile and used by the Accountability Agent to calibrate language style.
- **Account creation:** simple auth via Supabase (email or OAuth) — minimal friction, no lengthy forms.

## 2. Multi-Agent Coaching System

### 2.1 Planner Agent
- Decomposes goals into milestones with realistic target dates
- Breaks the nearest milestone into specific daily/weekly actions
- Re-plans automatically when a milestone is completed early/late
- Incorporates `reflection_notes` from the Reflection Agent to route around known friction points (e.g., reschedules around days the user historically struggles)

### 2.2 Accountability Agent
- Tracks check-ins against the active plan in real time
- **Escalation ladder:** calibrated response to missed check-ins —
  1. On-time → silent positive reinforcement (stack grows)
  2. One miss → warm, specific notification referencing the actual plan item
  3. Two consecutive misses → gentler check-in tone, asks if something's wrong
  4. Three+ misses, no response → autonomous decision to escalate to a **voice call** (see §5)
- **Comeback handling:** explicitly reframes returning after a gap as a positive event — never "you broke your streak"
- Generates all user-facing language itself — no canned/static notification templates

### 2.3 Reflection Agent
- Runs on a periodic cycle (e.g., weekly) over check-in history
- Detects behavioral patterns: best/worst days, time-of-day performance, common excuses or blockers
- Cross-references qualitative notes (vector store) with structured check-in data
- Produces `reflection_notes` that measurably change the next planning cycle — the core proof that "the system remembers and adapts"
- Surfaces optional gentle social prompts for Shared Circles (e.g., noticing a circle member has gone quiet)

### 2.4 Game Master Agent
- Bridges agent decisions and the visual world
- Validates and enriches structured events (`AgentEvent`) with metadata (difficulty, variant tags)
- Passes events to the deterministic Tsumiki Engine — itself never directly renders or decides visuals (a deliberate separation of "judgment" vs. "guaranteed behavior")

## 3. Memory & Personalization (the core differentiator)

- **Hybrid memory architecture:**
  - Relational store (Supabase/Postgres): goals, milestones, check-ins, plans, world state — structured, queryable, fast
  - Vector store (Chroma): qualitative reflections and notes, retrieved by semantic similarity
- **Narrow, typed retrieval:** each agent queries only the slice of memory relevant to its task — never dumps full history into a prompt (this is what keeps responses specific instead of vague, and keeps token costs low)
- **Long-horizon recall:** the system can accurately reference something the user did or said weeks ago — demoable live by inspecting the database mid-presentation
- **Adaptive personalization loop:** Reflection → Planner feedback loop means the system's behavior visibly changes over time based on the individual user — not a static, generic experience

## 4. Tsumiki Visual Progress System (Gamification Engine)

- **Stacked-stone metaphor:** progress shown as a small, growing stack of stones — calm, balanced, intentional (no loud RPG bars, no shame-based streak counters)
- **Stone variants by event type:**
  - `milestone_reached` → new stone added, sized/colored by difficulty
  - `streak_maintained` → existing stack visually reinforced/steadied
  - `setback_recovered` → a distinct "resilient" stone — comebacks are marked positively, not penalized
  - `support_received` → a visually distinct "gifted" stone from a circle member
- **Deterministic engine:** plain rules-based code (no LLM) converts structured events into visual state — guarantees reliable, repeatable behavior for live demos and real use
- **Seasonal/ambient detail (stretch goal):** subtle background changes (light, color palette) over time to reinforce the calm, living-world feeling without adding complex assets

## 5. Voice Escalation (Vapi integration)

- Triggered autonomously by the Accountability Agent — not a static reminder rule
- **Personalized script generation:** call content is generated live from the user's actual goal and check-in history (not a generic "don't forget!" message)
- **Vapi handles the channel** (telephony via Twilio, STT/TTS); Tsumiki's agents remain the "brain" supplying content and making the escalation decision
- **Closed feedback loop:** call outcome (answered/voicemail/response) is logged back into memory, so the system learns how the user responds to escalation over time
- **Reliability safeguard:** thoroughly pre-tested flow + recorded backup clip for live demo conditions

## 6. Shared Circles (Social Layer)

- **Small, invite-based groups** — not public leaderboards, not stranger-matching
- **Side-by-side stacks:** circle members' progress visualizations shown together — presence, not competition
- **"Stone of support":** a single, wordless gesture — one tap sends quiet encouragement that appears as a small, distinctly-marked addition to a friend's stack
- **Agent-mediated nudges:** Reflection Agent can gently surface "X has been quiet — want to send support?" — connecting people without guilt-tripping either party
- **No rankings, scores, or comparisons** — explicitly designed to avoid the competitive-pressure patterns common in gamified apps

## 7. Mobile App (Native Android — built via Google AI Studio)

- Native Kotlin/Jetpack Compose app generated and iterated via Google AI Studio's app-building mode
- Core screens: goal setup, daily check-in, stack visualization (home), reflection/insights view, circle view, settings
- Calls out to the Tsumiki backend API (LangGraph agent orchestration + Supabase) over HTTP — the app is the client; the multi-agent system is the brain
- In-browser emulator + ADB install used for rapid iteration during the build window

## 8. Landing Page (Next.js)

- Single, polished marketing page: what Tsumiki is, the problem it solves, screenshots/demo clip, install link
- Built to make the project look like a shipped product (directly serves the "real products" judging criterion)
- Minimal scope — static content, fast to produce, high visual payoff

## 9. Dashboard / Live Demo Console (Next.js + Supabase Realtime)

- **Not a duplicate of the mobile app** — a judge-facing instrument that visualizes the system itself
- Live view of the LangGraph state object as it updates between agent hand-offs
- Real-time feed of memory-store reads/writes (via Supabase Realtime subscriptions)
- Visual mirror of Tsumiki Engine events translating into stack changes, synced with the mobile app
- This is the centerpiece of the "we are not an AI wrapper" proof — turning an architectural claim into something judges watch happen live

## 10. Settings, Privacy & Account

- Notification tone/frequency preferences
- Escalation level controls (e.g., opt out of voice calls, adjust the miss-threshold before escalation)
- Circle management (create/join/leave groups, manage who can send support)
- Data visibility controls — what's shared with circle members vs. fully private
- Account management via Supabase Auth

## 11. Platform & Infrastructure

- **Frontend (mobile):** Google AI Studio–generated native Android app (Kotlin/Jetpack Compose)
- **Frontend (web):** Next.js — landing page + live demo dashboard
- **Backend/orchestration:** LangGraph (explicit multi-agent state graph) deployed as an API service (e.g., Cloud Run)
- **LLM layer:** Ollama Cloud running gemma4:31b, swapped per-agent as needed
- **Data layer:** Supabase (Postgres relational store + Auth + Realtime) and Chroma (vector store for semantic memory)
- **Voice layer:** Vapi (telephony, STT/TTS) for autonomous escalation calls
- **Gamification layer:** custom deterministic rules engine (plain code, fully unit-tested, zero LLM dependency)

---

## Feature Priority for the 4-Day Build

**Must-have (core demo path):**
Goal setup → Planner → Accountability → check-ins → Game Master → Tsumiki Engine → visible stack change → Reflection feedback loop

**High-value (differentiation moments):**
Live dashboard showing agent hand-offs and memory updates; voice escalation demo

**Nice-to-have (if time allows):**
Shared Circles, seasonal/ambient visual detail, settings depth

This ordering ensures that even if time runs short, the demoable core — the thing that proves "real multi-agent system, not a wrapper" — is always intact.
