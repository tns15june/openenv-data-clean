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
from typing import Any, Dict, List, Optional

from openai import OpenAI
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")

TASKS = ["customer_contacts", "sales_records", "employee_records", "financial_transactions"]

# ---------------------------------------------------------------------------
# System prompt — Plan-Then-Execute strategy
# ---------------------------------------------------------------------------
PLANNING_PROMPT = textwrap.dedent("""\
    You are an expert data quality analyst. You will be given:
    1. A dataset with known quality issues
    2. Inspection results for every column
    3. Validation rules

    Your job: Analyze ALL the data and produce a COMPLETE fix plan as a JSON array.

    OUTPUT FORMAT — respond with ONLY a JSON array, no other text:
    [
      {"action": "fix", "row": 3, "column": "email", "value": "alice@mail.com"},
      {"action": "fix", "row": 7, "column": "phone", "value": "555-012-3408"},
      {"action": "delete", "row": 14},
      ...
    ]

    RULES:
    - Emails: user@domain.tld format (no [at], no @@, no spaces)
    - Phone numbers: digits and dashes only, at least 10 digits
    - Dates: YYYY-MM-DD format, must be valid calendar date
    - Empty/missing values: provide a reasonable value matching the column context
    - Negative numbers: make them positive (absolute value)
    - Outliers: fix to a reasonable value within the stated range
    - Inconsistent names/categories: use the EXACT canonical form from the task description
    - Excess whitespace: trim and collapse double spaces
    - Currency codes: use ISO format (USD, EUR, GBP, JPY, CAD)
    - Manager/reviewer IDs: must reference an existing valid ID
    - Performance scores: within 0.0-10.0
    - Salaries: within $20,000-$500,000
    - Termination dates: must be after hire date, or empty if active
    - Approved/flagged transactions: must have a reviewer_id
    - Duplicates: use "delete" action on the LATER duplicate row

    CRITICAL — DELETION ORDER:
    List ALL fix actions first, then ALL delete actions.
    Delete rows from HIGHEST index to LOWEST (to avoid index shifting).

    IMPORTANT: Only fix cells that actually have issues. Do NOT touch correct data.
    Be conservative — a wrong fix costs -0.05 penalty.

    Respond with ONLY the JSON array. No explanation, no markdown fences, no other text.
""")


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def env_reset(task_id: str) -> Dict[str, Any]:
    resp = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def env_step(command: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{ENV_URL}/step",
        json={"action": {"command": command}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# JSON plan extraction
# ---------------------------------------------------------------------------
def extract_json_plan(text: str) -> Optional[List[Dict]]:
    """Extract a JSON array from LLM response, handling markdown fences."""
    if not text:
        return None
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    try:
        plan = json.loads(text)
        if isinstance(plan, list):
            return plan
    except json.JSONDecodeError:
        pass
    # Try to find JSON array in the text
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            plan = json.loads(match.group())
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass
    return None


def plan_to_command(action: Dict) -> Optional[str]:
    """Convert a plan action dict to an environment command string."""
    act_type = action.get("action", "")
    if act_type == "fix":
        row = action.get("row", 0)
        col = action.get("column", "")
        val = action.get("value", "")
        return f'fix({row}, "{col}", "{val}")'
    elif act_type == "delete":
        row = action.get("row", 0)
        return f"delete({row})"
    return None


# ---------------------------------------------------------------------------
# Fallback: single-action extraction for error recovery
# ---------------------------------------------------------------------------
ACTION_RE = re.compile(r"(inspect|fix|delete|submit)\s*\(", re.IGNORECASE)


def extract_action(response_text: str) -> str:
    if not response_text:
        return "submit()"
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^```\w*\s*", "", line)
        line = re.sub(r"\s*```$", "", line)
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
# Format observation for LLM context
# ---------------------------------------------------------------------------
def format_observation(obs: Dict[str, Any]) -> str:
    parts = [
        f"Task: {obs.get('task_id', '?')} ({obs.get('difficulty', '?')})",
        f"Total issues: {obs.get('total_issues', 0)}",
        "",
        "Task description:",
        obs.get("task_description", ""),
        "",
        "Column info:",
        obs.get("column_info", ""),
        "",
        "Current data:",
        obs.get("data_preview", ""),
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main — Plan-Then-Execute
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
        if done:
            results[task_id] = obs.get("current_score", 0.0)
            continue

        total_issues = obs.get("total_issues", 0)
        max_steps = obs.get("actions_remaining", 0)

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
        step_count = 0
        for col in columns:
            if done:
                break
            step_count += 1
            cmd = f'inspect("{col}")'
            print(f"  Step {step_count}: {cmd}")
            obs = env_step(cmd)
            if "observation" in obs:
                obs = obs["observation"]
            done = obs.get("done", False)
            inspection_results.append(obs.get("feedback", ""))

        if done:
            results[task_id] = obs.get("current_score", 0.0)
            print(f"  Done during inspection. Score: {results[task_id]:.4f}")
            continue

        # --- Phase 2: Ask LLM to plan ALL fixes in ONE call ---
        context = format_observation(obs)
        inspection_text = "\n\n".join(
            f"[Column: {col}]\n{result}"
            for col, result in zip(columns, inspection_results)
        )

        planning_message = (
            f"{context}\n\n"
            f"--- INSPECTION RESULTS ---\n{inspection_text}\n\n"
            f"--- PLAN YOUR FIXES ---\n"
            f"Remaining steps: {obs.get('actions_remaining', 0)} (includes submit).\n"
            f"Total issues to fix: {total_issues}.\n"
            f"Output ONLY a JSON array of fix/delete actions."
        )

        print(f"  Calling LLM for fix plan...")
        try:
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": PLANNING_PROMPT},
                    {"role": "user", "content": planning_message},
                ],
                temperature=0.0,
                max_tokens=2000,
                stream=False,
            )
            plan_text = completion.choices[0].message.content or ""
        except Exception as exc:
            print(f"  LLM error: {exc}. Submitting.")
            env_step("submit()")
            obs_final = env_step("submit()")
            if "observation" in obs_final:
                obs_final = obs_final["observation"]
            results[task_id] = obs_final.get("current_score", 0.0)
            continue

        plan = extract_json_plan(plan_text)
        if not plan:
            print(f"  Failed to parse JSON plan. Falling back to single-action mode.")
            # Degraded recovery: use the LLM response as individual actions
            # Re-query LLM in single-action mode for remaining steps
            fallback_messages = [
                {"role": "system", "content": (
                    "You are a data quality analyst. Respond with EXACTLY ONE command per turn.\n"
                    "Commands: inspect(\"col\"), fix(row, \"col\", \"val\"), delete(row), submit()\n"
                    "Respond with ONLY the command. No explanation."
                )},
                {"role": "user", "content": planning_message},
            ]
            remaining = obs.get("actions_remaining", 0)
            while not done and remaining > 0:
                try:
                    comp = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=fallback_messages,
                        temperature=0.0,
                        max_tokens=300,
                        stream=False,
                    )
                    resp_text = comp.choices[0].message.content or ""
                except Exception:
                    resp_text = "submit()"
                action_cmd = extract_action(resp_text)
                fallback_messages.append({"role": "assistant", "content": action_cmd})
                step_count += 1
                print(f"  Step {step_count} (fallback): {action_cmd}")
                obs = env_step(action_cmd)
                if "observation" in obs:
                    obs = obs["observation"]
                done = obs.get("done", False)
                remaining = obs.get("actions_remaining", 0)
                if not done:
                    fb = obs.get("feedback", "")
                    fallback_messages.append({"role": "user", "content": f"Result: {fb}\nIssues fixed: {obs.get('issues_fixed',0)}/{obs.get('total_issues',0)}. Actions remaining: {remaining}. Next command?"})
                if len(fallback_messages) > 30:
                    fallback_messages = [fallback_messages[0]] + fallback_messages[-28:]
            results[task_id] = obs.get("current_score", 0.0)
            print(f"  Final score for {task_id}: {results[task_id]:.4f}")
            continue

        print(f"  Plan has {len(plan)} actions.")

        # --- Phase 3: Execute plan ---
        remaining = obs.get("actions_remaining", 0)
        for i, action_item in enumerate(plan):
            if done or remaining <= 1:  # Save 1 step for submit
                break

            cmd = plan_to_command(action_item)
            if not cmd:
                continue

            step_count += 1
            remaining -= 1
            print(f"  Step {step_count}: {cmd}")
            obs = env_step(cmd)
            if "observation" in obs:
                obs = obs["observation"]
            done = obs.get("done", False)
            remaining = obs.get("actions_remaining", 0)

            feedback = obs.get("feedback", "")
            if "not yet resolved" in feedback.lower() and not done:
                # Fix didn't work — we'll continue with the plan, no retry to save steps
                print(f"    Warning: {feedback[:80]}")

        # --- Phase 4: Submit ---
        if not done:
            step_count += 1
            print(f"  Step {step_count}: submit()")
            obs = env_step("submit()")
            if "observation" in obs:
                obs = obs["observation"]

        score = obs.get("current_score", 0.0)
        results[task_id] = score
        print(f"  Final score for {task_id}: {score:.4f}")

    # --- Results Summary ---
    print(f"\n{'=' * 60}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 60}")
    for task_id, score in results.items():
        print(f"  {task_id}: {score:.4f}")
    avg = sum(results.values()) / len(results) if results else 0.0
    print(f"  Average: {avg:.4f}")


if __name__ == "__main__":
    main()
