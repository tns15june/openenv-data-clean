"""DataClean Environment — core logic."""

import copy
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from openenv.core.env_server.types import Action, Observation, State

try:
    from openenv.core.env_server.interfaces import Environment
except ImportError:
    from openenv.core.env_server import Environment

try:
    from ..models import DataCleanAction, DataCleanObservation, DataCleanState
    from .action_parser import ParsedAction, parse_action
    from .graders import (
        VALIDATORS,
        validate_date_format,
        validate_row_deleted,
        validate_temporal_order,
    )
    from .tasks import Issue, TaskDefinition, get_task
except ImportError:
    from models import DataCleanAction, DataCleanObservation, DataCleanState
    from server.action_parser import ParsedAction, parse_action
    from server.graders import (
        VALIDATORS,
        validate_date_format,
        validate_row_deleted,
        validate_temporal_order,
    )
    from server.tasks import Issue, TaskDefinition, get_task


def _format_table(data: List[Dict[str, Any]], columns: List[str], max_rows: int = 50) -> str:
    """Format data as a readable text table."""
    if not data:
        return "(empty dataset)"

    # Calculate column widths
    widths: Dict[str, int] = {}
    for col in columns:
        widths[col] = max(
            len(col),
            *(len(str(row.get(col, ""))) for row in data[:max_rows]),
        )
        widths[col] = min(widths[col], 30)  # cap width

    # Header
    hdr = "| row | " + " | ".join(col.ljust(widths[col]) for col in columns) + " |"
    sep = "|-----|" + "|".join("-" * (widths[col] + 2) for col in columns) + "|"
    lines = [hdr, sep]

    for i, row in enumerate(data[:max_rows]):
        vals = []
        for col in columns:
            v = str(row.get(col, ""))
            if len(v) > 30:
                v = v[:27] + "..."
            vals.append(v.ljust(widths[col]))
        lines.append(f"| {str(i).rjust(3)} | " + " | ".join(vals) + " |")

    if len(data) > max_rows:
        lines.append(f"... ({len(data) - max_rows} more rows)")

    return "\n".join(lines)


def _column_stats(data: List[Dict[str, Any]], column: str) -> str:
    """Generate stats for a single column."""
    values = [row.get(column, "") for row in data]
    total = len(values)
    non_null = sum(1 for v in values if v is not None and str(v).strip() != "")
    unique = len(set(str(v) for v in values))

    lines = [
        f"Column: {column}",
        f"  Total rows: {total}",
        f"  Non-empty: {non_null}",
        f"  Unique values: {unique}",
    ]

    # Try numeric stats
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except (ValueError, TypeError):
            pass

    if nums and len(nums) > total * 0.5:
        lines.append(f"  Min: {min(nums)}")
        lines.append(f"  Max: {max(nums)}")
        lines.append(f"  Mean: {sum(nums) / len(nums):.2f}")
    else:
        # Show sample values for string columns
        samples = sorted(set(str(v) for v in values if v is not None and str(v).strip()))[:8]
        lines.append(f"  Sample values: {samples}")

    # Flag suspicious values
    suspicious = []
    for i, v in enumerate(values):
        sv = str(v).strip()
        if sv == "" or sv.lower() in ("none", "null", "nan"):
            suspicious.append(f"Row {i}: empty/null")
        elif "  " in sv:
            suspicious.append(f"Row {i}: excess whitespace")
    if suspicious:
        lines.append(f"  Suspicious: {suspicious[:5]}")

    return "\n".join(lines)


class DataCleanEnvironment(Environment):
    """Data quality analysis and cleaning environment."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        super().__init__()
        self._state = DataCleanState(episode_id=str(uuid4()))
        self._task: Optional[TaskDefinition] = None
        self._current_data: List[Dict[str, Any]] = []
        self._issue_status: Dict[str, bool] = {}  # issue_id → resolved
        self._damaged_cells: int = 0
        self._actions_taken: List[str] = []
        self._inspected_columns: Set[str] = set()
        self._score: float = 0.0
        self._done: bool = False
        # Track which cells are known-bad (in issue registry) to detect damage
        self._bad_cells: Set[tuple] = set()  # (row, column)
        # For row deletion tracking — map original rows by index
        self._row_index_map: List[int] = []  # current_idx → original_idx

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> DataCleanObservation:
        task_id = kwargs.get("task_id", "customer_contacts")
        self._task = get_task(task_id, seed=seed)

        self._current_data = copy.deepcopy(self._task.data)
        self._issue_status = {issue.issue_id: False for issue in self._task.issues}
        self._damaged_cells = 0
        self._actions_taken = []
        self._inspected_columns = set()
        self._score = 0.0
        self._done = False
        self._row_index_map = list(range(len(self._current_data)))

        # Track which cells are in the issue registry
        self._bad_cells = set()
        for issue in self._task.issues:
            if issue.issue_type != "duplicate_row" and issue.column:
                self._bad_cells.add((issue.row, issue.column))

        self._state = DataCleanState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=self._task.task_id,
            difficulty=self._task.difficulty,
            total_issues=len(self._task.issues),
            fixed_issues=0,
            damaged_cells=0,
            max_steps=self._task.max_steps,
            score=0.0,
        )

        return self._build_observation(
            feedback=f"Task '{self._task.task_id}' loaded ({self._task.difficulty}). "
            f"Dataset has {len(self._current_data)} rows, {len(self._task.columns)} columns, "
            f"and {len(self._task.issues)} known issues to fix. "
            f"You have {self._task.max_steps} steps. Use inspect() to examine columns, "
            f"fix() to correct values, delete() for duplicates, submit() when done."
        )

    def step(
        self,
        action: DataCleanAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> DataCleanObservation:
        if self._task is None:
            return self._build_observation(
                feedback="Error: No task loaded. Call reset(task_id=...) first.",
                done=True,
            )

        if self._done:
            return self._build_observation(
                feedback="Episode already finished. Call reset() to start a new one.",
                done=True,
            )

        self._state.step_count += 1
        self._actions_taken.append(action.command)

        parsed = parse_action(action.command)

        if parsed.command_type == "error":
            feedback = f"Parse error: {parsed.error_message}"
        elif parsed.command_type == "submit":
            feedback = self._handle_submit()
        elif parsed.command_type == "inspect":
            feedback = self._handle_inspect(parsed)
        elif parsed.command_type == "fix":
            feedback = self._handle_fix(parsed)
        elif parsed.command_type == "delete":
            feedback = self._handle_delete(parsed)
        else:
            feedback = f"Unknown command type: {parsed.command_type}"

        # Check step limit
        remaining = self._task.max_steps - self._state.step_count
        if remaining <= 0 and not self._done:
            self._done = True
            self._compute_final_score()
            feedback += f"\n\nMax steps reached. Final score: {self._score:.4f}"

        self._state.fixed_issues = sum(1 for v in self._issue_status.values() if v)
        self._state.damaged_cells = self._damaged_cells
        self._state.score = self._score

        return self._build_observation(feedback=feedback)

    @property
    def state(self) -> DataCleanState:
        return self._state

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _handle_submit(self) -> str:
        self._done = True
        self._compute_final_score()
        fixed = sum(1 for v in self._issue_status.values() if v)
        total = len(self._task.issues)
        return (
            f"Submitted! Fixed {fixed}/{total} issues. "
            f"Damaged cells: {self._damaged_cells}. "
            f"Final score: {self._score:.4f}"
        )

    def _handle_inspect(self, parsed: ParsedAction) -> str:
        col = parsed.args["column"]
        if col not in self._task.columns:
            return (
                f"Column '{col}' not found. "
                f"Available: {self._task.columns}"
            )

        self._inspected_columns.add(col)
        stats = _column_stats(self._current_data, col)
        desc = self._task.column_descriptions.get(col, "")

        # Count issues in this column
        col_issues = [
            i for i in self._task.issues
            if i.column == col and not self._issue_status.get(i.issue_id, False)
        ]
        hint = f"\n  Issues remaining in this column: {len(col_issues)}"

        return f"Inspecting '{col}' ({desc}):\n{stats}{hint}"

    def _handle_fix(self, parsed: ParsedAction) -> str:
        row_idx = parsed.args["row"]
        col = parsed.args["column"]
        new_value = parsed.args["value"]

        if row_idx < 0 or row_idx >= len(self._current_data):
            return f"Row {row_idx} out of range (0-{len(self._current_data) - 1})"

        if col not in self._task.columns:
            return f"Column '{col}' not found. Available: {self._task.columns}"

        # Get the original row index (to match issue registry)
        orig_idx = self._row_index_map[row_idx]
        old_value = self._current_data[row_idx].get(col, "")

        # Check if this cell is in the issue registry
        cell_in_issue = (orig_idx, col) in self._bad_cells

        if not cell_in_issue:
            # Agent is modifying a cell that had no known issue — damage
            self._current_data[row_idx][col] = new_value
            self._damaged_cells += 1
            self._recompute_score()
            return (
                f"Warning: Row {row_idx}, column '{col}' had no known issue. "
                f"Original value '{old_value}' was overwritten. Penalty applied (-0.05)."
            )

        # Apply the fix
        # Try to convert to appropriate type
        converted = self._convert_value(new_value, old_value)
        self._current_data[row_idx][col] = converted

        # Check all issues involving this cell
        reward_delta = 0.0
        fixed_any = False
        for issue in self._task.issues:
            if issue.row != orig_idx or issue.column != col:
                continue
            if self._issue_status.get(issue.issue_id, False):
                continue  # already resolved

            if self._check_issue_resolved(issue):
                self._issue_status[issue.issue_id] = True
                reward_delta += 1.0 / len(self._task.issues)
                fixed_any = True

        self._recompute_score()

        if fixed_any:
            return (
                f"Fixed: Row {row_idx}, '{col}' changed from '{old_value}' to '{converted}'. "
                f"Score: {self._score:.4f}"
            )
        else:
            return (
                f"Changed: Row {row_idx}, '{col}' from '{old_value}' to '{converted}', "
                f"but the issue is not yet resolved. Check the expected format. "
                f"Score: {self._score:.4f}"
            )

    def _handle_delete(self, parsed: ParsedAction) -> str:
        row_idx = parsed.args["row"]

        if row_idx < 0 or row_idx >= len(self._current_data):
            return f"Row {row_idx} out of range (0-{len(self._current_data) - 1})"

        orig_idx = self._row_index_map[row_idx]
        deleted_row = self._current_data[row_idx]

        # Check if this row is a known duplicate
        is_duplicate = False
        for issue in self._task.issues:
            if issue.issue_type != "duplicate_row":
                continue
            if issue.row != orig_idx:
                continue
            if self._issue_status.get(issue.issue_id, False):
                continue

            self._issue_status[issue.issue_id] = True
            is_duplicate = True

        if not is_duplicate:
            # Deleting a non-duplicate row — penalty
            self._damaged_cells += 1

        # Actually remove the row
        self._current_data.pop(row_idx)
        self._row_index_map.pop(row_idx)

        self._recompute_score()

        if is_duplicate:
            return (
                f"Deleted duplicate row {row_idx}. Score: {self._score:.4f}"
            )
        else:
            return (
                f"Warning: Row {row_idx} was not a known duplicate. "
                f"Penalty applied (-0.05). Score: {self._score:.4f}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_issue_resolved(self, issue: Issue) -> bool:
        """Check if an issue is resolved in the current data."""
        if issue.issue_type == "duplicate_row":
            # Row is resolved if it was deleted (no longer in index map)
            return self._find_current_row(issue.row) is None

        if issue.issue_type == "temporal_inconsistency":
            current_row_idx = self._find_current_row(issue.row)
            if current_row_idx is None:
                return False
            row = self._current_data[current_row_idx]
            hire = str(row.get("hire_date", ""))
            term = str(row.get("termination_date", ""))
            return validate_temporal_order(hire, term)

        if issue.issue_type == "cross_column_violation":
            current_row_idx = self._find_current_row(issue.row)
            if current_row_idx is None:
                return False
            row = self._current_data[current_row_idx]
            status = str(row.get("status", "")).strip().lower()
            reviewer = str(row.get("reviewer_id", "")).strip()
            if status in ("approved", "flagged"):
                return reviewer != "" and reviewer.lower() not in ("none", "null", "")
            return True

        # Standard validation
        validator = VALIDATORS.get(issue.issue_type)
        if validator is None:
            return False

        current_row_idx = self._find_current_row(issue.row)
        if current_row_idx is None:
            return False

        val = self._current_data[current_row_idx].get(issue.column, "")
        return validator(val, **issue.validation_params)

    def _find_current_row(self, original_idx: int) -> Optional[int]:
        """Find current row index from original index."""
        try:
            return self._row_index_map.index(original_idx)
        except ValueError:
            return None  # row was deleted

    def _convert_value(self, new_value: str, old_value: Any) -> Any:
        """Try to convert new_value to match the type of old_value."""
        if isinstance(old_value, int):
            try:
                return int(float(new_value))
            except (ValueError, TypeError):
                return new_value
        if isinstance(old_value, float):
            try:
                return float(new_value)
            except (ValueError, TypeError):
                return new_value
        return new_value

    def _recompute_score(self) -> None:
        """Recompute running score based on current issue states and damage."""
        total = len(self._task.issues)
        if total == 0:
            self._score = 1.0
            return
        resolved = sum(1 for v in self._issue_status.values() if v)
        self._score = resolved / total
        self._score = max(0.0, self._score - self._damaged_cells * 0.05)
        self._score = min(1.0, self._score)

    def _compute_final_score(self) -> None:
        """Recompute score based on all current issue states."""
        total = len(self._task.issues)
        if total == 0:
            self._score = 1.0
            return

        resolved = 0
        for issue in self._task.issues:
            if self._issue_status.get(issue.issue_id, False):
                resolved += 1
                continue
            # One last check in case fixes propagated
            if self._check_issue_resolved(issue):
                self._issue_status[issue.issue_id] = True
                resolved += 1

        self._score = resolved / total
        # Apply damage penalty
        self._score = max(0.0, self._score - self._damaged_cells * 0.05)
        self._score = min(1.0, self._score)

    def _build_observation(
        self, feedback: str = "", done: Optional[bool] = None,
    ) -> DataCleanObservation:
        if done is None:
            done = self._done

        task = self._task
        if task is None:
            return DataCleanObservation(
                done=done,
                reward=self._score,
                feedback=feedback,
            )

        fixed = sum(1 for v in self._issue_status.values() if v)
        remaining = max(0, task.max_steps - self._state.step_count)

        col_info_parts = []
        for col in task.columns:
            desc = task.column_descriptions.get(col, "")
            col_info_parts.append(f"  {col}: {desc}")
        col_info = "\n".join(col_info_parts)

        return DataCleanObservation(
            done=done,
            reward=self._score,
            task_id=task.task_id,
            task_description=task.description,
            difficulty=task.difficulty,
            data_preview=_format_table(self._current_data, task.columns),
            column_info=col_info,
            feedback=feedback,
            actions_remaining=remaining,
            issues_found=len(self._inspected_columns),
            issues_fixed=fixed,
            total_issues=len(task.issues),
            current_score=round(self._score, 4),
            action_history=list(self._actions_taken[-10:]),
        )
