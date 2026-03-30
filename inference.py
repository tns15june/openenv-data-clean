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
MAX_TOKENS = 150

TASKS = ["customer_contacts", "sales_records", "employee_records"]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = textwrap.dedent("""\
    You are a data quality analyst. You are given a dataset with known issues.
    Your job is to find and fix all data quality problems.

    Available commands (respond with EXACTLY ONE command per turn, no explanation):
      inspect("column_name")                — View column statistics and issues
      fix(row_index, "column_name", "value") — Fix a specific cell value
      delete(row_index)                      — Remove a duplicate/invalid row
      submit()                               — Finalize and get your score

    Strategy:
    1. Start by inspecting columns to understand the data and find issues
    2. Fix issues one by one using the fix() command
    3. For duplicate rows, use delete() on the duplicate (usually the later row)
    4. After fixing all issues, use submit()

    Rules for fixes:
    - Emails: must be user@domain.tld format
    - Phone numbers: digits and dashes only, at least 10 digits
    - Dates: must be YYYY-MM-DD format and valid
    - Empty/missing values: provide a reasonable non-empty value
    - Negative numbers (quantity/price): make them positive
    - Outliers: fix to a reasonable value within the stated range
    - Inconsistent names: use the exact canonical form stated in the task
    - Excess whitespace: trim and remove double spaces
    - Manager IDs: must reference an existing employee ID in the dataset
    - Performance scores: must be within 0.0-10.0
    - Salaries: must be within $20,000-$500,000
    - Termination dates: must be after hire date (or empty if active)

    IMPORTANT: After deleting a row, all subsequent row indices shift down by 1.
    Account for this when fixing or deleting later rows.

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

        step_num = 0
        while not done:
            step_num += 1
            user_msg = format_observation(obs, step_num)
            messages.append({"role": "user", "content": user_msg})

            # Keep conversation manageable
            if len(messages) > 20:
                messages = [messages[0]] + messages[-18:]

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
                reward = obs.get("reward", score)
                print(f"  Done! Score: {score:.4f}")
                results[task_id] = score

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
