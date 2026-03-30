"""
Inference Script — DataCleanEnv
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables
"""

import json
import os
import re
import sys
import textwrap
from typing import Any, Dict, List

from openai import OpenAI

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")

TEMPERATURE = 0.0
MAX_TOKENS = 300

TASKS = ["customer_contacts", "sales_records", "employee_records"]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert data quality analyst. You are given a dataset with known issues.
    Your job is to find and fix ALL data quality problems efficiently.

    Available commands (respond with EXACTLY ONE command per turn, no explanation):
      inspect("column_name")                — View column statistics and issues
      fix(row_index, "column_name", "value") — Fix a specific cell value
      delete(row_index)                      — Remove a duplicate/invalid row
      submit()                               — Finalize and get your score

    STRATEGY (follow this order strictly):
    1. You will first receive inspection results for all columns — read them carefully
    2. Look at the data table and identify ALL issues based on the inspection hints
    3. Fix ALL issues using fix() commands, one at a time
    4. Delete duplicate rows LAST (after all fixes), from highest row index to lowest
       (this avoids row index shifting problems)
    5. Only call submit() when you believe ALL issues are fixed

    VALIDATION RULES:
    - Emails: must match user@domain.tld (no [at], no @@, no spaces)
    - Phone numbers: digits, dashes, parens, spaces only; at least 10 digits
    - Dates: YYYY-MM-DD format (e.g., 2024-03-25), must be valid calendar date
    - Empty/missing values: provide a reasonable non-empty value matching context
    - Negative numbers (quantity/price): make them positive (use absolute value)
    - Price/salary outliers: fix to a reasonable value within the stated range
    - Inconsistent region/department names: use the EXACT canonical form from the task description
    - Excess whitespace: trim leading/trailing spaces, collapse double spaces to single
    - Manager IDs: must reference an existing employee emp_id in the dataset
    - Performance scores: must be within 0.0-10.0
    - Salaries: must be within $20,000-$500,000
    - Termination dates: must be AFTER hire date, or leave empty if employee is active
    - Duplicate rows: rows that are exact or near-exact copies — delete the LATER one

    IMPORTANT: After deleting a row, all subsequent row indices shift down by 1.
    Always delete from highest index to lowest to avoid this issue.

    Respond with ONLY the command. No explanation, no markdown, no extra text.
""")


# ---------------------------------------------------------------------------
# HTTP helpers (direct REST calls to the environment server)
# ---------------------------------------------------------------------------
import requests


def env_reset(task_id: str) -> Dict[str, Any]:
    """Reset the environment with a specific task."""
    resp = requests.post(
        f"{ENV_URL}/reset",
        json={"task_id": task_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def env_step(command: str) -> Dict[str, Any]:
    """Execute a command in the environment."""
    resp = requests.post(
        f"{ENV_URL}/step",
        json={"action": {"command": command}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Observation formatting
# ---------------------------------------------------------------------------
def format_observation(obs: Dict[str, Any], step_num: int) -> str:
    """Format an observation dict as a user message for the LLM."""
    parts = []
    parts.append(f"Step {step_num} | Task: {obs.get('task_id', '?')} ({obs.get('difficulty', '?')})")
    parts.append(f"Issues fixed: {obs.get('issues_fixed', 0)}/{obs.get('total_issues', 0)} | Score: {obs.get('current_score', 0.0):.4f}")
    parts.append(f"Actions remaining: {obs.get('actions_remaining', 0)}")
    parts.append("")

    feedback = obs.get("feedback", "")
    if feedback:
        parts.append(f"Last action result: {feedback}")
        parts.append("")

    parts.append("Task description:")
    parts.append(obs.get("task_description", ""))
    parts.append("")

    parts.append("Column info:")
    parts.append(obs.get("column_info", ""))
    parts.append("")

    parts.append("Current data:")
    parts.append(obs.get("data_preview", ""))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Action extraction
# ---------------------------------------------------------------------------
ACTION_RE = re.compile(r"(inspect|fix|delete|submit)\s*\(", re.IGNORECASE)


def extract_action(response_text: str) -> str:
    """Extract a valid action from the LLM response."""
    if not response_text:
        return "submit()"

    # Try each line
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip markdown code fences
        line = re.sub(r"^```\w*\s*", "", line)
        line = re.sub(r"\s*```$", "", line)
        # Strip "action:" prefix
        line = re.sub(r"^(?:action|next action)\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
        if ACTION_RE.search(line):
            m = ACTION_RE.search(line)
            start = m.start()
            depth = 0
            for i in range(start, len(line)):
                if line[i] == "(":
                    depth += 1
                elif line[i] == ")":
                    depth -= 1
                    if depth == 0:
                        return line[start : i + 1]
            return line[start:] + ")"

    return "submit()"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    results = {}

    for task_id in TASKS:
        print(f"\n{'=' * 60}")
        print(f"Task: {task_id}")
        print(f"{'=' * 60}")

        obs = env_reset(task_id)
        if "observation" in obs:
            obs = obs["observation"]

        done = obs.get("done", False)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # --- Phase 1: Auto-inspect all columns ---
        columns = []
        col_info = obs.get("column_info", "")
        for line in col_info.strip().splitlines():
            line = line.strip()
            if ":" in line:
                col_name = line.split(":")[0].strip()
                if col_name:
                    columns.append(col_name)

        inspection_results = []
        step_num = 0
        for col in columns:
            if done:
                break
            step_num += 1
            cmd = f'inspect("{col}")'
            print(f"  Step {step_num}: {cmd}")
            obs = env_step(cmd)
            if "observation" in obs:
                obs = obs["observation"]
            done = obs.get("done", False)
            feedback = obs.get("feedback", "")
            inspection_results.append(f"[{col}]: {feedback}")

        if done:
            score = obs.get("current_score", 0.0)
            print(f"  Done during inspection! Score: {score:.4f}")
            results[task_id] = score
            continue

        # Build a summary of all inspections for the LLM
        inspection_summary = "\n\n".join(inspection_results)
        initial_context = format_observation(obs, step_num)
        initial_context += f"\n\n--- INSPECTION SUMMARY (all columns) ---\n{inspection_summary}"
        initial_context += "\n\n--- NOW FIX ALL ISSUES. Do fixes first, then deletions (highest index first). ---"

        messages.append({"role": "user", "content": initial_context})

        # --- Phase 2: LLM-driven fixes ---
        while not done:
            step_num += 1

            # Keep conversation manageable — but preserve system + initial context
            if len(messages) > 40:
                messages = [messages[0], messages[1]] + messages[-36:]

            try:
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=False,
                )
                response_text = completion.choices[0].message.content or ""
            except Exception as exc:
                print(f"  LLM error: {exc}. Using submit().")
                response_text = "submit()"

            action = extract_action(response_text)
            messages.append({"role": "assistant", "content": action})
            print(f"  Step {step_num}: {action}")

            obs = env_step(action)
            if "observation" in obs:
                obs = obs["observation"]

            done = obs.get("done", False)
            score = obs.get("current_score", 0.0)

            if done:
                print(f"  Done! Score: {score:.4f}")
                results[task_id] = score
            else:
                # Send updated observation as next user message
                user_msg = format_observation(obs, step_num)
                messages.append({"role": "user", "content": user_msg})

        print(f"  Final score for {task_id}: {results.get(task_id, 0.0):.4f}")

    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    for task_id, score in results.items():
        print(f"  {task_id}: {score:.4f}")
    avg = sum(results.values()) / len(results) if results else 0.0
    print(f"  Average: {avg:.4f}")


if __name__ == "__main__":
    main()
