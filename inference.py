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

This script emits exactly these stdout line types:
- [START] ...
- [STEP]  ... (one per step)
- [END]   ... (always)
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

from client import DataCleanEnv
from models import DataCleanAction, DataCleanObservation

# ---------------------------------------------------------------------------
# Config — read at import time but API vars re-read in main() to catch
# late-injected env vars from the validator.
# ---------------------------------------------------------------------------
BENCHMARK_URL = os.getenv(
    "BENCHMARK_URL",
    os.getenv("ENV_URL", "https://tns-openenv-data-clean.hf.space"),
)
BENCHMARK = os.getenv("BENCHMARK", "data_clean_env")

TASKS = ["customer_contacts", "sales_records", "employee_records", "financial_transactions"]

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: str | None) -> None:
    err = _single_line(error) if error else "null"
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={err}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    reward_csv = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={reward_csv}",
        flush=True,
    )


def _single_line(text: str | None) -> str:
    return (text or "").replace("\n", " ").replace("\r", " ").strip()


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
# Run a single task
# ---------------------------------------------------------------------------
def run_task(client: OpenAI, env, task_id: str, model_name: str = "") -> None:
    rewards: list[float] = []
    step_count = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=model_name)

    try:
        # --- Reset ---
        result = env.reset(task_id=task_id)
        obs = result.observation
        done = result.done

        if done:
            score = obs.current_score
            return

        total_issues = obs.total_issues

        # --- Phase 1: Auto-inspect all columns ---
        columns = []
        for line in obs.column_info.strip().splitlines():
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
            result = env.step(DataCleanAction(command=cmd))
            obs = result.observation
            done = result.done
            reward = float(result.reward or 0.0)
            rewards.append(reward)

            log_step(step=step_count, action=cmd, reward=reward, done=done, error=None)

            inspection_results[col] = obs.feedback

        if done:
            score = obs.current_score
            success = score >= 0.5
            return

        # --- Phase 1.5: Filter to only columns WITH issues ---
        flagged_inspections = {}
        for col, feedback in inspection_results.items():
            m = re.search(r"Issues remaining in this column:\s*(\d+)", feedback)
            issue_count = int(m.group(1)) if m else 0
            if issue_count > 0:
                flagged_inspections[col] = feedback

        for col, feedback in inspection_results.items():
            if col not in flagged_inspections and "Suspicious:" in feedback:
                flagged_inspections[col] = feedback

        # --- Phase 2: Ask LLM to plan fixes ---
        if flagged_inspections:
            inspection_text = "\n\n".join(
                f"[{col}]\n{fb}" for col, fb in flagged_inspections.items()
            )
        else:
            inspection_text = "(No specific column issues flagged. Check for duplicate rows.)"

        planning_message = (
            f"Task: {obs.task_id} ({obs.difficulty})\n"
            f"Total issues to find and fix: {total_issues}\n\n"
            f"Task description:\n{obs.task_description}\n\n"
            f"Column definitions:\n{obs.column_info}\n\n"
            f"FLAGGED COLUMNS (only fix cells in these columns or duplicate rows):\n{inspection_text}\n\n"
            f"Current data:\n{obs.data_preview}\n\n"
            f"Produce a JSON array with EXACTLY the fixes needed. "
            f"Expected: around {total_issues} actions (fixes + deletes). "
            f"Do NOT produce more than {total_issues + 3} actions."
        )

        try:
            completion = client.chat.completions.create(
                model=model_name,
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
            # LLM error — submit immediately
            step_count += 1
            cmd = "submit()"
            result = env.step(DataCleanAction(command=cmd))
            obs = result.observation
            done = result.done
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            log_step(step=step_count, action=cmd, reward=reward, done=True, error=_single_line(str(exc)))
            score = obs.current_score
            return

        plan = extract_json_plan(plan_text)

        # --- Sanity check: reject bloated plans ---
        if plan and len(plan) > total_issues + 5:
            plan = plan[:total_issues + 3]

        if not plan:
            # --- Fallback: single-action mode ---
            fallback_messages = [
                {"role": "system", "content": (
                    "You are a data quality analyst. Respond with EXACTLY ONE command per turn.\n"
                    "Commands: inspect(\"col\"), fix(row, \"col\", \"val\"), delete(row), submit()\n"
                    "ONLY fix cells with actual issues. Do NOT fix correct data.\n"
                    "Respond with ONLY the command."
                )},
                {"role": "user", "content": planning_message},
            ]
            remaining = obs.actions_remaining
            while not done and remaining > 0:
                try:
                    comp = client.chat.completions.create(
                        model=model_name,
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
                result = env.step(DataCleanAction(command=action_cmd))
                obs = result.observation
                done = result.done
                reward = float(result.reward or 0.0)
                rewards.append(reward)
                log_step(step=step_count, action=action_cmd, reward=reward, done=done, error=None)
                remaining = obs.actions_remaining
                if not done:
                    fb = obs.feedback
                    fallback_messages.append({"role": "user", "content": f"Result: {fb}\nFixed: {obs.issues_fixed}/{obs.total_issues}. Remaining steps: {remaining}."})
                if len(fallback_messages) > 30:
                    fallback_messages = [fallback_messages[0]] + fallback_messages[-28:]
            score = obs.current_score
            success = score >= 0.5
            return

        # --- Phase 3: Execute plan ---
        remaining = obs.actions_remaining
        for action_item in plan:
            if done or remaining <= 1:
                break
            cmd = plan_to_command(action_item)
            if not cmd:
                continue
            step_count += 1
            result = env.step(DataCleanAction(command=cmd))
            obs = result.observation
            done = result.done
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            log_step(step=step_count, action=cmd, reward=reward, done=done, error=None)
            remaining = obs.actions_remaining

        # --- Phase 4: Submit ---
        if not done:
            step_count += 1
            cmd = "submit()"
            result = env.step(DataCleanAction(command=cmd))
            obs = result.observation
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            log_step(step=step_count, action=cmd, reward=reward, done=True, error=None)

        score = obs.current_score
        success = score >= 0.5

    except Exception as exc:
        log_step(step=step_count + 1, action="error", reward=0.0, done=True, error=_single_line(str(exc)))
        success = False
    finally:
        log_end(success=success, steps=step_count, score=score, rewards=rewards)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    import sys

    # Read API vars fresh — validator injects these at runtime
    api_base_url = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
    api_key = os.environ.get("API_KEY") or os.environ.get("HF_TOKEN", "")
    model_name = os.environ.get("MODEL_NAME", "")

    # Debug: log config to stderr (never stdout — validator parses that)
    print(f"[CONFIG] API_BASE_URL={api_base_url}", file=sys.stderr, flush=True)
    print(f"[CONFIG] API_KEY={'set('+api_key[:8]+'...)' if api_key else 'EMPTY'}", file=sys.stderr, flush=True)
    print(f"[CONFIG] MODEL_NAME={model_name}", file=sys.stderr, flush=True)
    print(f"[CONFIG] BENCHMARK_URL={BENCHMARK_URL}", file=sys.stderr, flush=True)

    client = OpenAI(base_url=api_base_url, api_key=api_key)

    env_client = DataCleanEnv(base_url=BENCHMARK_URL)
    with env_client.sync() as env:
        for task_id in TASKS:
            run_task(client, env, task_id, model_name)


if __name__ == "__main__":
    main()
