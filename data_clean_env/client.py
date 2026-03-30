"""DataClean Environment Client."""

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

from .models import DataCleanAction, DataCleanObservation, DataCleanState


class DataCleanEnv(EnvClient[DataCleanAction, DataCleanObservation, DataCleanState]):
    """Client for interacting with a DataClean environment server.

    Example:
        >>> with DataCleanEnv(base_url="http://localhost:8000").sync() as env:
        ...     result = env.reset(task_id="customer_contacts")
        ...     print(result.observation.data_preview)
        ...     result = env.step(DataCleanAction(command='inspect("email")'))
        ...     result = env.step(DataCleanAction(command='fix(3, "email", "test@example.com")'))
        ...     result = env.step(DataCleanAction(command='submit()'))
        ...     print(f"Score: {result.observation.current_score}")
    """

    def _step_payload(self, action: DataCleanAction) -> dict:
        return action.model_dump()

    def _parse_result(self, payload: dict) -> StepResult[DataCleanObservation]:
        obs = DataCleanObservation(**payload.get("observation", payload))
        return StepResult(
            observation=obs,
            reward=obs.reward,
            done=obs.done,
        )

    def _parse_state(self, payload: dict) -> DataCleanState:
        return DataCleanState(**payload)
