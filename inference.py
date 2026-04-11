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
# System prompt — Conservative plan-then-execute
# ---------------------------------------------------------------------------
PLANNING_PROMPT = textwrap.dedent("""\
    You are a data quality analyst. You will receive a dataset, inspection results,
    and validation rules. Produce a PRECISE fix plan as a JSON array.

    CRITICAL RULES:
    - ONLY fix cells that inspection flagged as having issues (suspicious values, wrong format, etc.)
    - If inspection shows "Issues remaining in this column: 0", do NOT touch that column
    - Do NOT fix cells that already have correct values
    - Each wrong fix costs -0.05 penalty. Be CONSERVATIVE.
    - For duplicate rows (two identical rows), use "delete" on the LATER row
    - List all "fix" actions first, then all "delete" actions
    - Delete from highest row index to lowest

    VALIDATION RULES:
    - Emails: user@domain.tld (no [at], no @@, no spaces, no missing domain)
    - Phones: digits and dashes only, 10+ digits (no letters)
    - Dates: YYYY-MM-DD only (not MM/DD/YYYY, not slashes, valid calendar date)
    - Empty values: provide a reasonable non-empty value
    - Negative numbers: use the absolute value (make positive)
    - Outliers: fix to a reasonable mid-range value within the stated bounds
    - Inconsistent format: use the EXACT canonical form listed in the task description
    - Whitespace: trim leading/trailing, collapse double spaces to single
    - Salaries: must be $20,000-$500,000
    - Performance scores: must be 0.0-10.0
    - Currency: must be ISO code (USD, EUR, GBP, JPY, CAD)
    - Reviewer IDs: approved/flagged status requires a reviewer_id

    OUTPUT: Respond with ONLY a JSON array. No explanation, no markdown, no text before or after.

    EXAMPLE for a 3-issue dataset:
    [{"action":"fix","row":3,"column":"email","value":"alice@mail.com"},{"action":"fix","row":7,"column":"phone","value":"555-012-3408"},{"action":"delete","row":14}]
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
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    try:
        plan = json.loads(text)
        if isinstance(plan, list):
            return plan
    except json.JSONDecodeError:
        pass
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
    act_type = action.get("action", "")
    if act_type == "fix":
        row = action.get("row", 0)
        col = action.get("column", "")
        val = str(action.get("value", ""))
        return f'fix({row}, "{col}", "{val}")'
    elif act_type == "delete":
        row = action.get("row", 0)
        return f"delete({row})"
    return None


# ---------------------------------------------------------------------------
# Fallback: single-action extraction
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
# Main — Plan-Then-Execute
# ---------------------------------------------------------------------------
def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    results = {}

    for task_id in TASKS:
        print(f"\n{'=' * 60}")
        print(f"Task: {task_id}")
        print(f"{'=' * 60}")
        print(f"[START] task={task_id}", flush=True)

        obs = env_reset(task_id)
        if "observation" in obs:
            obs = obs["observation"]

        step_count = 0
        done = obs.get("done", False)
        if done:
            score = obs.get("current_score", 0.0)
            results[task_id] = score
            print(f"[END] task={task_id} score={score} steps=0", flush=True)
            continue

        total_issues = obs.get("total_issues", 0)

        # --- Phase 1: Auto-inspect all columns ---
        columns = []
        col_info = obs.get("column_info", "")
        for line in col_info.strip().splitlines():
            line = line.strip()
            if ":" in line:
                col_name = line.split(":")[0].strip()
                if col_name:
                    columns.append(col_name)

        inspection_results = {}
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
            reward = obs.get("current_score", 0.0)
            print(f"[STEP] step={step_count} reward={reward}", flush=True)
            feedback = obs.get("feedback", "")
            inspection_results[col] = feedback

        if done:
            score = obs.get("current_score", 0.0)
            results[task_id] = score
            print(f"  Done during inspection. Score: {score:.4f}")
            print(f"[END] task={task_id} score={score} steps={step_count}", flush=True)
            continue

        # --- Phase 1.5: Filter to only columns WITH issues ---
        flagged_inspections = {}
        for col, feedback in inspection_results.items():
            # Extract "Issues remaining in this column: N"
            m = re.search(r"Issues remaining in this column:\s*(\d+)", feedback)
            issue_count = int(m.group(1)) if m else 0
            if issue_count > 0:
                flagged_inspections[col] = feedback

        # Also check for suspicious values in inspection even if issue count is 0
        for col, feedback in inspection_results.items():
            if col not in flagged_inspections and "Suspicious:" in feedback:
                flagged_inspections[col] = feedback

        print(f"  Columns with issues: {list(flagged_inspections.keys())} ({len(flagged_inspections)}/{len(columns)})")

        # --- Phase 2: Ask LLM to plan fixes ---
        # Only show the LLM columns that have issues + the data table
        if flagged_inspections:
            inspection_text = "\n\n".join(
                f"[{col}]\n{fb}" for col, fb in flagged_inspections.items()
            )
        else:
            inspection_text = "(No specific column issues flagged. Check for duplicate rows.)"

        planning_message = (
            f"Task: {obs.get('task_id', '?')} ({obs.get('difficulty', '?')})\n"
            f"Total issues to find and fix: {total_issues}\n\n"
            f"Task description:\n{obs.get('task_description', '')}\n\n"
            f"Column definitions:\n{obs.get('column_info', '')}\n\n"
            f"FLAGGED COLUMNS (only fix cells in these columns or duplicate rows):\n{inspection_text}\n\n"
            f"Current data:\n{obs.get('data_preview', '')}\n\n"
            f"Produce a JSON array with EXACTLY the fixes needed. "
            f"Expected: around {total_issues} actions (fixes + deletes). "
            f"Do NOT produce more than {total_issues + 3} actions."
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
            step_count += 1
            obs = env_step("submit()")
            if "observation" in obs:
                obs = obs["observation"]
            score = obs.get("current_score", 0.0)
            results[task_id] = score
            print(f"[STEP] step={step_count} reward={score}", flush=True)
            print(f"[END] task={task_id} score={score} steps={step_count}", flush=True)
            continue

        plan = extract_json_plan(plan_text)

        # --- Sanity check: reject bloated plans ---
        if plan and len(plan) > total_issues + 5:
            print(f"  Plan too large ({len(plan)} actions for {total_issues} issues). Trimming to {total_issues + 3}.")
            plan = plan[:total_issues + 3]

        if not plan:
            print(f"  Failed to parse JSON plan. Falling back to single-action mode.")
            fallback_messages = [
                {"role": "system", "content": (
                    "You are a data quality analyst. Respond with EXACTLY ONE command per turn.\n"
                    "Commands: inspect(\"col\"), fix(row, \"col\", \"val\"), delete(row), submit()\n"
                    "ONLY fix cells with actual issues. Do NOT fix correct data.\n"
                    "Respond with ONLY the command."
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
                reward = obs.get("current_score", 0.0)
                print(f"[STEP] step={step_count} reward={reward}", flush=True)
                remaining = obs.get("actions_remaining", 0)
                if not done:
                    fb = obs.get("feedback", "")
                    fallback_messages.append({"role": "user", "content": f"Result: {fb}\nFixed: {obs.get('issues_fixed',0)}/{obs.get('total_issues',0)}. Remaining steps: {remaining}."})
                if len(fallback_messages) > 30:
                    fallback_messages = [fallback_messages[0]] + fallback_messages[-28:]
            score = obs.get("current_score", 0.0)
            results[task_id] = score
            print(f"  Final score for {task_id}: {score:.4f}")
            print(f"[END] task={task_id} score={score} steps={step_count}", flush=True)
            continue

        print(f"  Plan has {len(plan)} actions (expected ~{total_issues}).")

        # --- Phase 3: Execute plan ---
        remaining = obs.get("actions_remaining", 0)
        for i, action_item in enumerate(plan):
            if done or remaining <= 1:
                break

            cmd = plan_to_command(action_item)
            if not cmd:
                continue

            step_count += 1
            print(f"  Step {step_count}: {cmd}")
            obs = env_step(cmd)
            if "observation" in obs:
                obs = obs["observation"]
            done = obs.get("done", False)
            reward = obs.get("current_score", 0.0)
            print(f"[STEP] step={step_count} reward={reward}", flush=True)
            remaining = obs.get("actions_remaining", 0)

            feedback = obs.get("feedback", "")
            if "not yet resolved" in feedback.lower() and not done:
                print(f"    Warning: {feedback[:80]}")

        # --- Phase 4: Submit ---
        if not done:
            step_count += 1
            print(f"  Step {step_count}: submit()")
            obs = env_step("submit()")
            if "observation" in obs:
                obs = obs["observation"]
            reward = obs.get("current_score", 0.0)
            print(f"[STEP] step={step_count} reward={reward}", flush=True)

        score = obs.get("current_score", 0.0)
        results[task_id] = score
        print(f"  Final score for {task_id}: {score:.4f}")
        print(f"[END] task={task_id} score={score} steps={step_count}", flush=True)

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
