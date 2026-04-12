from typing import Any, Dict, List, Optional

from pydantic import Field

from openenv.core.env_server.types import Action, Observation, State


class DataCleanAction(Action):
    """A string command for data cleaning operations.

    Supported commands:
        inspect("column_name") - View column statistics and issue hints
        fix(row, "column", "new_value") - Correct a cell value
        delete(row) - Remove a duplicate/invalid row
        submit() - Finalize and get scored
    """

    command: str = Field(
        ..., min_length=1, description="Command string to execute"
    )


class DataCleanObservation(Observation):
    """Observation returned after each step.

    `done` and `reward` are inherited from the OpenEnv Observation base. They
    are redeclared here so callers can see the full schema without inspecting
    the framework, and so breaking upstream changes surface as type errors.
    """

    done: bool = Field(default=False)
    reward: float = Field(default=0.0)
    task_id: str = Field(default="")
    task_description: str = Field(default="")
    difficulty: str = Field(default="easy")
    data_preview: str = Field(default="", description="Formatted text table of current data")
    column_info: str = Field(default="", description="Column names, types, and stats")
    feedback: str = Field(default="", description="Result of last action")
    actions_remaining: int = Field(default=0)
    issues_found: int = Field(default=0)
    issues_fixed: int = Field(default=0)
    total_issues: int = Field(default=0)
    current_score: float = Field(default=0.0)
    action_history: List[str] = Field(default_factory=list)


class DataCleanState(State):
    """Full environment state."""

    task_id: str = Field(default="")
    difficulty: str = Field(default="easy")
    total_issues: int = Field(default=0)
    fixed_issues: int = Field(default=0)
    damaged_cells: int = Field(default=0)
    max_steps: int = Field(default=15)
    score: float = Field(default=0.0)
