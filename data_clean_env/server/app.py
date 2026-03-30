"""FastAPI application for the DataClean Environment."""

from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

try:
    from .environment import DataCleanEnvironment
    from ..models import DataCleanAction, DataCleanObservation
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.environment import DataCleanEnvironment
    from models import DataCleanAction, DataCleanObservation

app = FastAPI(title="DataCleanEnv", version="1.0.0")

# Shared stateful environment instance
_env = DataCleanEnvironment()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reset")
async def reset(request: ResetRequest = Body(default_factory=ResetRequest)):
    obs = _env.reset(seed=request.seed, episode_id=request.episode_id, task_id=request.task_id)
    return {"observation": _obs_dict(obs), "reward": None, "done": False}


@app.post("/step")
async def step(request: StepRequest):
    action = DataCleanAction(**request.action)
    obs = _env.step(action)
    return {"observation": _obs_dict(obs), "reward": obs.reward, "done": obs.done}


@app.get("/state")
async def state():
    return _env.state.model_dump()


@app.get("/metadata")
async def metadata():
    return {
        "env_name": "data_clean_env",
        "action_schema": DataCleanAction.model_json_schema(),
        "observation_schema": DataCleanObservation.model_json_schema(),
    }


@app.get("/schema")
async def schema():
    return {
        "action": DataCleanAction.model_json_schema(),
        "observation": DataCleanObservation.model_json_schema(),
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
