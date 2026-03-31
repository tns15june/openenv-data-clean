"""
Training Script — DataCleanEnv + TRL GRPO
==========================================
Train an LLM agent to clean data using Group Relative Policy Optimization.

Prerequisites:
    pip install trl datasets transformers torch

Usage:
    # Start the environment server first:
    uvicorn server.app:app --host 0.0.0.0 --port 8000

    # Then run training:
    python train.py

    # With custom model:
    python train.py --model "Qwen/Qwen3-0.6B" --env-url "http://localhost:8000"

Environment variables:
    ENV_URL     Environment server URL (default: http://localhost:8000)
"""

import argparse
import os
from typing import List

import requests

ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")


class DataCleanToolEnv:
    """TRL-compatible environment factory for data cleaning.

    Exposes data cleaning operations as individual tool methods with
    docstrings that TRL's GRPOTrainer auto-discovers for function calling.

    Each tool method communicates with the running DataCleanEnv server
    and updates self.reward with the current episode score.
    """

    def __init__(self):
        self.reward = 0.0
        self._env_url = ENV_URL
        self._task_id = "customer_contacts"
        self._seed = None

    def _step(self, command: str) -> str:
        resp = requests.post(
            f"{self._env_url}/step",
            json={"action": {"command": command}},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        obs = data.get("observation", data)
        self.reward = obs.get("current_score", 0.0)
        return obs.get("feedback", "")

    def reset(self, **kwargs) -> str:
        """Reset the environment with a new data cleaning task.

        Returns the task description, column info, and full data table
        so the agent has complete context for planning fixes.
        """
        self._task_id = kwargs.get("task_id", self._task_id)
        self._seed = kwargs.get("seed", None)
        self.reward = 0.0

        payload = {"task_id": self._task_id}
        if self._seed is not None:
            payload["seed"] = self._seed

        resp = requests.post(
            f"{self._env_url}/reset",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        obs = data.get("observation", data)

        return (
            f"Task: {obs.get('task_description', '')}\n\n"
            f"Columns:\n{obs.get('column_info', '')}\n\n"
            f"Data:\n{obs.get('data_preview', '')}\n\n"
            f"Total issues to fix: {obs.get('total_issues', 0)}. "
            f"Actions remaining: {obs.get('actions_remaining', 0)}."
        )

    def inspect(self, column: str) -> str:
        """Inspect a column to see statistics and detect data quality issues.

        Use this to understand the data before fixing. Returns column statistics
        including row count, unique values, suspicious entries, and issue hints.

        Args:
            column: The column name to inspect (e.g., "email", "phone", "salary")

        Returns:
            Column statistics and quality issue indicators.
        """
        return self._step(f'inspect("{column}")')

    def fix(self, row: int, column: str, value: str) -> str:
        """Fix a data quality issue by correcting a cell value.

        Use this after identifying issues via inspect(). Provide the corrected
        value that satisfies the column's validation rules.

        Args:
            row: The row index (0-based) of the cell to fix
            column: The column name of the cell to fix
            value: The corrected value to set

        Returns:
            Confirmation of the fix, whether the issue was resolved, and updated score.
        """
        return self._step(f'fix({row}, "{column}", "{value}")')

    def delete(self, row: int) -> str:
        """Delete a duplicate or invalid row from the dataset.

        Use this only for rows that are exact duplicates. Delete from highest
        index to lowest to avoid index shifting issues.

        Args:
            row: The row index (0-based) to delete

        Returns:
            Confirmation of deletion and whether it was a valid duplicate removal.
        """
        return self._step(f"delete({row})")

    def submit(self) -> str:
        """Submit the cleaned dataset for final scoring.

        Call this after fixing all identified issues. Returns the final score
        and summary of what was fixed vs. missed.

        Returns:
            Final score and episode summary.
        """
        return self._step("submit()")


def reward_func(environments: List[DataCleanToolEnv], **kwargs) -> List[float]:
    """Extract rewards from completed environments."""
    return [env.reward for env in environments]


def main():
    parser = argparse.ArgumentParser(description="Train a data cleaning agent with TRL GRPO")
    parser.add_argument("--model", default="Qwen/Qwen3-0.6B", help="Model to fine-tune")
    parser.add_argument("--env-url", default=ENV_URL, help="Environment server URL")
    parser.add_argument("--num-episodes", type=int, default=64, help="Training episodes")
    parser.add_argument("--output-dir", default="./output", help="Output directory")
    args = parser.parse_args()

    global ENV_URL
    ENV_URL = args.env_url

    try:
        from datasets import Dataset
        from trl import GRPOConfig, GRPOTrainer
    except ImportError:
        print("TRL not installed. Install with: pip install trl datasets transformers torch")
        print("\nThis script requires a GPU for training. The DataCleanToolEnv class")
        print("can also be used standalone for agent evaluation:")
        print("\n  env = DataCleanToolEnv()")
        print('  obs = env.reset(task_id="customer_contacts", seed=42)')
        print('  result = env.inspect("email")')
        print('  result = env.fix(3, "email", "alice@mail.com")')
        print('  result = env.submit()')
        print(f"  print(env.reward)  # -> score between 0.0 and 1.0")
        return

    # Build training dataset with prompts for each difficulty level
    tasks = ["customer_contacts", "sales_records", "employee_records", "financial_transactions"]
    n_per_task = args.num_episodes // len(tasks)

    prompts = []
    task_ids = []
    seeds = []
    for task_id in tasks:
        for i in range(n_per_task):
            prompts.append([{
                "role": "user",
                "content": (
                    f"Clean the {task_id.replace('_', ' ')} dataset. "
                    "Inspect columns to find issues, fix all data quality problems, "
                    "delete duplicates, then submit for scoring. "
                    "Be precise and conservative — wrong fixes are penalized."
                ),
            }])
            task_ids.append(task_id)
            seeds.append(i + 1)  # Different seed per episode for diversity

    dataset = Dataset.from_dict({
        "prompt": prompts,
        "task_id": task_ids,
        "seed": seeds,
    })

    print(f"Training {args.model} on {len(dataset)} episodes across {len(tasks)} tasks")
    print(f"Environment: {args.env_url}")

    trainer = GRPOTrainer(
        model=args.model,
        train_dataset=dataset,
        reward_funcs=reward_func,
        args=GRPOConfig(
            output_dir=args.output_dir,
            max_completion_length=4096,
            num_generations=4,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            logging_steps=1,
            log_completions=True,
            report_to="none",
        ),
        environment_factory=DataCleanToolEnv,
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    print(f"Model saved to {args.output_dir}")


if __name__ == "__main__":
    main()
