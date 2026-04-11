"""
Evaluation / Benchmark Script — DataCleanEnv
=============================================
Run any model across all tasks and report scores.

Usage:
    # Start the environment server first:
    uvicorn server.app:app --host 0.0.0.0 --port 8000

    # Evaluate with default settings:
    python eval.py

    # Evaluate a specific model:
    python eval.py --model "meta-llama/Llama-3.1-8B-Instruct"

    # Evaluate with seed variation (multiple runs):
    python eval.py --seeds 5 --tasks customer_contacts sales_records

    # JSON output for CI/programmatic use:
    python eval.py --json

Environment variables:
    API_BASE_URL   LLM API endpoint
    MODEL_NAME     Model identifier
    HF_TOKEN       API key
    ENV_URL        Environment server URL
"""

import argparse
import json
import os
import re
import statistics
import sys
import textwrap
from typing import Any, Dict, List, Optional

import requests
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")

ALL_TASKS = ["customer_contacts", "sales_records", "employee_records", "financial_transactions"]

PLANNING_PROMPT = textwrap.dedent("""\
    You are an expert data quality analyst. Analyze the dataset and produce
    a COMPLETE fix plan as a JSON array. Output ONLY the JSON array.

    Format: [{"action": "fix", "row": N, "column": "col", "value": "val"}, {"action": "delete", "row": N}, ...]

    Rules: Emails must be user@domain.tld. Dates must be YYYY-MM-DD. Numbers must be positive.
    Use exact canonical forms from the task description. Delete duplicates (highest index first).
    List fixes first, then deletes. Only fix cells with actual issues.
""")


def env_reset(task_id: str, seed: Optional[int] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"task_id": task_id}
    if seed is not None:
        payload["seed"] = seed
    resp = requests.post(f"{ENV_URL}/reset", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("observation", data)


def env_step(command: str) -> Dict[str, Any]:
    resp = requests.post(f"{ENV_URL}/step", json={"action": {"command": command}}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("observation", data)


def extract_json_plan(text: str) -> Optional[List[Dict]]:
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


def run_task(client: OpenAI, model: str, task_id: str, seed: Optional[int] = None) -> float:
    """Run a single task and return the score."""
    obs = env_reset(task_id, seed=seed)
    if obs.get("done", False):
        return obs.get("current_score", 0.0)

    # Phase 1: Inspect all columns
    columns = []
    for line in obs.get("column_info", "").strip().splitlines():
        if ":" in line:
            col = line.strip().split(":")[0].strip()
            if col:
                columns.append(col)

    inspections = []
    for col in columns:
        obs = env_step(f'inspect("{col}")')
        if obs.get("done", False):
            return obs.get("current_score", 0.0)
        inspections.append(f"[{col}]: {obs.get('feedback', '')}")

    # Phase 2: Plan
    context = (
        f"Task: {obs.get('task_description', '')}\n"
        f"Columns:\n{obs.get('column_info', '')}\n"
        f"Data:\n{obs.get('data_preview', '')}\n\n"
        f"Inspections:\n" + "\n\n".join(inspections) + "\n\n"
        f"Remaining steps: {obs.get('actions_remaining', 0)}. Issues: {obs.get('total_issues', 0)}."
    )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": PLANNING_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.0,
            max_tokens=2000,
        )
        plan = extract_json_plan(completion.choices[0].message.content or "")
    except Exception:
        plan = None

    # Phase 3: Execute
    if plan:
        for action in plan:
            if obs.get("done", False) or obs.get("actions_remaining", 0) <= 1:
                break
            act_type = action.get("action", "")
            if act_type == "fix":
                cmd = f'fix({action["row"]}, "{action["column"]}", "{action["value"]}")'
            elif act_type == "delete":
                cmd = f'delete({action["row"]})'
            else:
                continue
            obs = env_step(cmd)

    # Submit
    if not obs.get("done", False):
        obs = env_step("submit()")

    return obs.get("current_score", 0.0)


def main():
    parser = argparse.ArgumentParser(description="Benchmark models on DataCleanEnv")
    parser.add_argument("--model", default=MODEL_NAME or "meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--tasks", nargs="*", default=ALL_TASKS)
    parser.add_argument("--seeds", type=int, default=1, help="Number of seeds per task (1 = no seed)")
    parser.add_argument("--env-url", default=ENV_URL)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    global ENV_URL
    ENV_URL = args.env_url

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    results: Dict[str, List[float]] = {}

    for task_id in args.tasks:
        scores = []
        seeds = [None] if args.seeds <= 1 else list(range(1, args.seeds + 1))
        for seed in seeds:
            seed_str = f" (seed={seed})" if seed else ""
            if not args.json:
                print(f"  Running {task_id}{seed_str}...", end=" ", flush=True)
            score = run_task(client, args.model, task_id, seed=seed)
            scores.append(score)
            if not args.json:
                print(f"{score:.4f}")
        results[task_id] = scores

    if args.json:
        report = {
            "model": args.model,
            "env_url": args.env_url,
            "results": {
                task: {"scores": scores, "mean": statistics.mean(scores),
                       "stdev": statistics.stdev(scores) if len(scores) > 1 else 0.0}
                for task, scores in results.items()
            },
            "average": statistics.mean(s for scores in results.values() for s in scores),
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"BENCHMARK RESULTS — {args.model}")
        print(f"{'='*60}")
        all_scores = []
        for task_id, scores in results.items():
            mean = statistics.mean(scores)
            all_scores.extend(scores)
            if len(scores) > 1:
                sd = statistics.stdev(scores)
                print(f"  {task_id:30s}  {mean:.4f} ± {sd:.4f}  (n={len(scores)})")
            else:
                print(f"  {task_id:30s}  {mean:.4f}")
        print(f"  {'AVERAGE':30s}  {statistics.mean(all_scores):.4f}")


if __name__ == "__main__":
    main()
