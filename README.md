# 🏯 Tsumiki — Agentic Habit & Goal Tracking

**Team Pixex | FAR AWAY 2026 — Agentic & Autonomous Systems**

[![GitHub Contributors](https://img.shields.io/github/contributors/Shrujal00/Tsumiki.svg)](https://github.com/Shrujal00/Tsumiki/graphs/contributors)
[![Built with LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Architecture-blue)](https://python.langchain.com/docs/langgraph/)
[![Supabase](https://img.shields.io/badge/Supabase-Relational_Memory-3ECF8E?logo=supabase)](https://supabase.com)
[![Next.js](https://img.shields.io/badge/Next.js-React_Framework-black?logo=next.js)](https://nextjs.org/)

Tsumiki is a premium, multi-agent AI system designed to coach you through building habits and achieving goals. Unlike traditional trackers that rely on loud gamification, red streaks, and guilt, Tsumiki uses an intelligent team of AI agents that understand context, adapt to your behavior, and actively help you route around friction points.

---

## 🌟 The "Why"
Traditional habit trackers are just dumb databases. They record your successes and punish your failures. Tsumiki is different. It acts as an **autonomous coaching team**:
1. **It plans for you**: Breaking massive goals into daily actions.
2. **It adapts to you**: If you constantly miss Mondays, it learns to schedule light days on Mondays.
3. **It intervenes**: If you fall off track, it autonomously escalates, eventually calling your actual phone to gently pull you back in.

## 🧠 The Architecture (Not an AI Wrapper)
Tsumiki is built on a robust, stateful **LangGraph** architecture. It is not a single prompt wrapped in a UI; it is an orchestrated graph of distinct AI agents acting on a hybrid memory store.

### The Agent Team
- **Planner Agent:** Decomposes natural-language goals into concrete, time-boxed milestones.
- **Accountability Agent:** Evaluates your adherence to the plan. Uses a deterministic escalation ladder to decide when to intervene, and generates warm, context-aware notification copy.
- **Game Master Agent:** Translates agent decisions into the visual world (determining difficulty tags and tracking streaks).
- **Reflection Agent:** Periodically analyzes your entire check-in history to extract long-term behavioral patterns (e.g., "High friction on Mondays").

### The Memory Layer
- **Relational Store (Supabase):** Tracks deterministic state like Goals, Check-ins, and user profiles.
- **Vector Store (ChromaDB):** Stores semantic memories and reflections, allowing the Planner to "remember" why you struggled 3 weeks ago.

### The Application Stack
- **Backend:** FastAPI, Python, LangGraph, Ollama Cloud (gemma4:31b).
- **Frontend:** Next.js (React), Tailwind CSS, Framer Motion (for beautiful, satisfying micro-animations).
- **Voice Escalation:** Vapi + Twilio for autonomous PSTN phone calls.

---

## 🛠️ Getting Started Locally

### Prerequisites
- Python 3.12+ (uv recommended)
- Node.js 20+
- Docker (optional, for backend deployment)

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env.local` inside `backend/` and populate it with your keys:
```env
SUPABASE_URL="your-supabase-url"
SUPABASE_SERVICE_ROLE_KEY="your-supabase-key"
LANGSMITH_TRACING=true
LANGSMITH_API_KEY="your-langsmith-key"
LANGSMITH_PROJECT="tsumiki-dev"
OLLAMA_API_KEY="your-ollama-key"
OLLAMA_MODEL="gemma4:31b-cloud"
VAPI_API_KEY="your-vapi-key"
VAPI_ASSISTANT_ID="your-vapi-assistant-id"
```

Start the API:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
The dashboard will be available at `http://localhost:3000`.

---

## 👥 Meet the Team (Pixex)
- **Shrujal (@Shrujal00):** Backend Engineering, Agent Architecture (LangGraph), and Memory Systems.
- **Karan (@UKaran2811):** Frontend Engineering, Next.js Dashboard, UI/UX, and Animations.

---

*Built for FAR AWAY 2026.* 🚀
