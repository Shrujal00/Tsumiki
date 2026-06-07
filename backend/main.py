"""Tsumiki backend — FastAPI entrypoint.

Exposes the health check plus the client-facing flows (goals, check-ins, state,
reflection, circle support) wired in ``api.py``. The agent/memory deps used by
those routes are imported lazily inside the service, so importing this module
stays cheap.
"""

from __future__ import annotations

from fastapi import FastAPI

from api import router as api_router
from config import get_settings

app = FastAPI(title="Tsumiki Backend", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    """Liveness probe plus a non-secret config echo.

    Returns only safe fields (model name, project, Supabase host). Never returns
    API keys, the service-role key, or the full Supabase URL.
    """
    settings = get_settings()
    return {"status": "ok", **settings.public_summary()}
