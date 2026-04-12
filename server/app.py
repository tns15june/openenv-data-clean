"""
FastAPI application for the DataClean Environment.

Uses the OpenEnv framework's create_app() for full feature support
(WebSocket, Web UI, MCP, OpenAPI docs) while patching in session-isolated
stateful HTTP endpoints for inference script compatibility.
"""

import asyncio
import os
from collections import OrderedDict
from uuid import uuid4

from fastapi import FastAPI, Body, Header
from pydantic import BaseModel
from typing import Any, Dict, Optional

# Enable the Gradio web interface before importing create_app
os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")

from openenv.core.env_server.http_server import create_app

try:
    from .environment import DataCleanEnvironment
    from ..models import DataCleanAction, DataCleanObservation
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.environment import DataCleanEnvironment
    from models import DataCleanAction, DataCleanObservation


# ---------------------------------------------------------------------------
# Create the full framework app (WebSocket /ws, Web UI /web/, MCP /mcp,
# OpenAPI /docs, /health, /metadata, /schema)
# ---------------------------------------------------------------------------
_framework_app = create_app(
    DataCleanEnvironment,
    DataCleanAction,
    DataCleanObservation,
    env_name="data_clean_env",
)

# Remove the framework's stateless /reset, /step, /state HTTP routes
# so we can replace them with session-isolated stateful versions below.
# This keeps WebSocket, web UI, MCP, /docs, /health, /metadata, /schema intact.
_framework_app.router.routes = [
    r for r in _framework_app.router.routes
    if not (
        hasattr(r, 'path') and hasattr(r, 'methods')
        and r.path in ('/reset', '/step', '/state')
    )
]

app = _framework_app


# ---------------------------------------------------------------------------
# Session-isolated stateful HTTP layer
#
# Each session gets its own DataCleanEnvironment instance. Sessions are
# identified by the X-Session-Id header (or auto-assigned on /reset).
# A default session ("default") is used when no header is provided,
# so simple single-client usage (like inference.py) works out of the box.
# ---------------------------------------------------------------------------
_sessions: "OrderedDict[str, DataCleanEnvironment]" = OrderedDict()
_sessions_lock = asyncio.Lock()

MAX_SESSIONS = 50


async def _get_or_create_session(session_id: str) -> DataCleanEnvironment:
    async with _sessions_lock:
        if session_id in _sessions:
            # Mark as most-recently-used so true-LRU eviction doesn't drop
            # an active session before an idle one.
            _sessions.move_to_end(session_id)
            return _sessions[session_id]
        if len(_sessions) >= MAX_SESSIONS:
            _sessions.popitem(last=False)
        _sessions[session_id] = DataCleanEnvironment()
        return _sessions[session_id]


class ResetRequest(BaseModel):
    task_id: str = "customer_contacts"
    seed: Optional[int] = None
    episode_id: Optional[str] = None
    model_config = {"extra": "allow"}


class StepRequest(BaseModel):
    action: Dict[str, Any]
    model_config = {"extra": "allow"}


def _obs_dict(obs: DataCleanObservation) -> dict:
    return obs.model_dump()


@app.post("/reset", tags=["Environment Control"])
async def stateful_reset(
    request: ResetRequest = Body(default_factory=ResetRequest),
    x_session_id: Optional[str] = Header(default="default"),
):
    """Reset the environment with a specific task. Session-isolated via X-Session-Id header."""
    session_id = x_session_id or "default"
    env = await _get_or_create_session(session_id)
    obs = env.reset(
        seed=request.seed,
        episode_id=request.episode_id,
        task_id=request.task_id,
    )
    return {"observation": _obs_dict(obs), "reward": None, "done": False}


@app.post("/step", tags=["Environment Control"])
async def stateful_step(
    request: StepRequest,
    x_session_id: Optional[str] = Header(default="default"),
):
    """Execute an action. Session-isolated via X-Session-Id header."""
    session_id = x_session_id or "default"
    env = await _get_or_create_session(session_id)
    action = DataCleanAction(**request.action)
    obs = env.step(action)
    return {"observation": _obs_dict(obs), "reward": obs.reward, "done": obs.done}


@app.get("/state", tags=["State Management"])
async def stateful_state(
    x_session_id: Optional[str] = Header(default="default"),
):
    """Get current environment state for a session."""
    session_id = x_session_id or "default"
    env = await _get_or_create_session(session_id)
    return env.state.model_dump()


# ---------------------------------------------------------------------------
# Entry point for `uv run server` / `python -m server.app`
# ---------------------------------------------------------------------------
def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
