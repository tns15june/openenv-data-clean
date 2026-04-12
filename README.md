---
title: DataCleanEnv
emoji: 🧹
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
tags:
  - openenv
  - rl-environment
  - data-cleaning
  - evaluation
  - trl
---

# DataCleanEnv — Data Quality Analysis & Cleaning Environment

A real-world OpenEnv environment where AI agents learn to identify and fix data quality issues through iterative inspection, correction, and validation.

## Motivation

Data cleaning is one of the most common and time-consuming tasks in data engineering. Analysts spend up to 80% of their time cleaning data before analysis. This environment trains and evaluates LLM agents on their ability to detect and fix real-world data quality problems — invalid formats, missing values, duplicates, outliers, referential integrity violations, and more.

## Action Space

Agents interact via string commands:

| Command | Description |
|---------|-------------|
| `inspect("column_name")` | View column statistics, sample values, and issue hints |
| `fix(row, "column", "value")` | Correct a specific cell value |
| `delete(row)` | Remove a duplicate or invalid row |
| `submit()` | Finalize work and receive final score |

## Observation Space

Each observation includes:

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Active task identifier |
| `task_description` | str | What the data represents and quality rules |
| `difficulty` | str | "easy", "medium", or "hard" |
| `data_preview` | str | Current dataset as formatted text table |
| `column_info` | str | Column names, types, and descriptions |
| `feedback` | str | Result of last action |
| `actions_remaining` | int | Steps left before auto-submit |
| `issues_fixed` | int | Count of resolved issues |
| `total_issues` | int | Total known issues in dataset |
| `current_score` | float | Running score (0.0–1.0) |
| `action_history` | list | Last 10 commands executed |

## Tasks

### Easy: Customer Contacts
- **15 rows, 5 columns** — name, email, phone, city, signup_date
- **6 issues**: invalid emails, phone with letters, empty city, wrong date format, duplicate row
- **15 max steps**

### Medium: Sales Records
- **30 rows, 7 columns** — order_id, customer_name, product, quantity, unit_price, order_date, region
- **12 issues**: mixed date formats, negative quantities/prices, price outliers, inconsistent region names, duplicates, missing IDs, excess whitespace
- **25 max steps**

### Hard: Employee Records
- **40 rows, 9 columns** — emp_id, name, email, department, hire_date, termination_date, salary, manager_id, performance_score
- **18 issues**: referential integrity violations (manager_id), temporal inconsistencies (termination before hire), salary outliers, invalid performance scores, department name inconsistencies, semantic duplicates, invalid dates, excess whitespace
- **35 max steps**

## Reward Design

- Each correctly fixed issue: **+1/total_issues**
- Damaging good data (fixing a cell that had no issue): **-0.05**
- Deleting a non-duplicate row: **-0.05**
- Inspect actions: no reward change (information gathering)
- Final score clamped to **[0.0, 1.0]**

Grading is **validation-based** (not exact match):
- Emails validated by regex pattern
- Dates checked for YYYY-MM-DD format and validity
- Numbers checked against allowed ranges
- Canonical values checked against defined sets
- Referential integrity checked against existing IDs

## Setup

### Local Development

```bash
# Install dependencies
pip install openenv-core fastapi uvicorn requests openai

# Run the server
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker build -t data-clean-env:latest .
docker run -d -p 8000:8000 data-clean-env:latest
```

### Running Inference

```bash
# Required — validator injects these during hackathon eval; set manually for local runs.
export API_BASE_URL="https://your-llm-endpoint/v1"   # LiteLLM proxy URL
export API_KEY="your-api-key"                         # LiteLLM proxy API key
export MODEL_NAME="your-model-name"

# Environment server URL. inference.py reads BENCHMARK_URL (falls back to
# ENV_URL, then the public HF Space). eval.py reads ENV_URL / --env-url.
export BENCHMARK_URL="http://localhost:8000"          # or your HF Space URL

# Optional toggles for inference.py:
#   DEBUG_CONFIG=1      — emit [CONFIG] diagnostics to stderr
#   SKIP_PROXY_PING=1   — skip the startup proxy ping in tight budgets

python inference.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/reset` | POST | Start new episode: `{"task_id": "customer_contacts"}` |
| `/step` | POST | Execute action: `{"action": {"command": "inspect(\"email\")"}}` |
| `/state` | GET | Get current environment state |
| `/docs` | GET | OpenAPI documentation |
| `/web/` | GET | Interactive Gradio web UI |
| `/ws` | WS | WebSocket for stateful agent sessions |
| `/mcp` | POST/WS | MCP tool support for compatible agents |

## Benchmark Results

Tested with plan-then-execute inference strategy across 4 models:

| Model | Easy | Medium | Hard | Expert | Average |
|-------|------|--------|------|--------|---------|
| Llama-3.3-70B-Instruct | **1.00** | **1.00** | **0.73** | **0.75** | **0.87** |
| Qwen2.5-72B-Instruct | 0.78 | 1.00 | 0.52 | 0.82 | 0.78 |
| DeepSeek-V3 | 1.00 | 0.87 | 0.33 | 0.00 | 0.55 |
| Llama-3.1-8B-Instruct | 0.73 | 0.00 | 0.00 | 0.00 | 0.18 |

Key findings:
- 70B+ models achieve near-perfect scores on easy/medium tasks
- Hard/expert tasks require strong multi-column reasoning
- Plan-then-execute strategy scales well with model capability

## Seed-Based Data Variation

Each task supports reproducible randomized episodes via the `seed` parameter:

```bash
# Deterministic (original data):
POST /reset {"task_id": "customer_contacts"}

# Randomized variant (same issue types, different corrupted rows):
POST /reset {"task_id": "customer_contacts", "seed": 42}
```

This enables RL training with diverse episodes — the agent must learn data cleaning *skills*, not memorize fixed answers.

## Training with TRL (GRPO)

The environment integrates with TRL's `GRPOTrainer` via the `DataCleanToolEnv` class in `train.py`:

```bash
# Start the server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# Run training
python train.py --model "Qwen/Qwen3-0.6B"
```

The tool environment exposes `inspect()`, `fix()`, `delete()`, `submit()` as individual methods with docstrings that TRL auto-discovers for function calling.

## Benchmarking

Evaluate any model across all tasks:

```bash
# Single evaluation
python eval.py --model "meta-llama/Llama-3.1-8B-Instruct"

# Multi-seed evaluation (measures variance)
python eval.py --seeds 5 --json

# Specific tasks only
python eval.py --tasks customer_contacts sales_records
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  DataCleanEnv                    │
├──────────┬──────────┬───────────┬───────────────┤
│ /reset   │ /step    │ /ws       │ /web/         │
│ /state   │ /health  │ /mcp      │ /docs         │
├──────────┴──────────┴───────────┴───────────────┤
│  server/environment.py — State Machine          │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐    │
│  │ tasks.py │  │graders.py│  │action_parse│    │
│  │ 4 tasks  │  │12 validators│ │robust parse│    │
│  │ + seeds  │  │          │  │            │    │
│  └──────────┘  └──────────┘  └────────────┘    │
├─────────────────────────────────────────────────┤
│  inference.py — Plan-Then-Execute Agent         │
│  train.py     — TRL GRPO Training Pipeline      │
│  eval.py      — Model Benchmarking              │
└─────────────────────────────────────────────────┘
```

## Technical Details

- **Framework**: OpenEnv (openenv-core 0.2.3)
- **Server**: FastAPI + Uvicorn
- **Data storage**: In-memory Python dicts (no database required)
- **Runtime**: < 20 min inference on 2 vCPU / 8GB RAM
- **Python**: 3.10+
