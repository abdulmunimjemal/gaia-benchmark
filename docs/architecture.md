# Architecture

## Overview

`gaia_bot` is a benchmark-oriented agent runtime. It combines:

- route selection
- web and attachment retrieval
- E2B code execution
- Anthropic Claude Agent SDK solve and verify passes
- deterministic result persistence

The current structure favors iteration speed over deep framework abstraction.

## Main Components

### Settings and entry points

- `src/gaia_bot/settings.py`
  - environment loading, validation, runtime defaults
- `src/gaia_bot/smoke.py`
  - live connectivity checks
- `src/gaia_bot/run.py`
  - single-task execution
- `src/gaia_bot/eval.py`
  - subset or full benchmark evaluation
- `src/gaia_bot/export_submission.py`
  - submission JSONL export
- `src/gaia_bot/compare_runs.py`
  - run-to-run comparison

### Agent runtime

- `src/gaia_bot/agent.py`
  - main solve loop
  - route selection
  - Claude Agent SDK structured query calls
  - verifier pass
  - runtime MCP tool exposure
- `src/gaia_bot/prompts.py`
  - benchmark-specific system and task prompts
- `src/gaia_bot/router.py`
  - heuristic task routing

### Retrieval and execution

- `src/gaia_bot/research.py`
  - web search and fetch helpers
- `src/gaia_bot/artifacts.py`
  - attachment and local-file extraction
- `src/gaia_bot/executor.py`
  - E2B sandbox wrapper

### Benchmark data and persistence

- `src/gaia_bot/benchmark.py`
  - local and Hugging Face dataset loading
- `src/gaia_bot/basemodels.py`
  - structured pydantic contracts for task, solver, trace, and submission data
- `src/gaia_bot/scoring.py`
  - answer extraction, formatting, and exact-match scoring
- `src/gaia_bot/results.py`
  - run directory creation, task result writes, summaries, and comparisons
- `src/gaia_bot/models.py`
  - compatibility re-export layer for older imports

## Runtime Flow

1. Load settings and dataset.
2. Select tasks by `task_id`, subset, or full run.
3. For each task:
   - determine a route
   - initialize attachment manager and sandbox runtime as needed
   - solve through Claude Agent SDK with repo-provided tools
   - optionally verify / retry
   - normalize final answer for benchmark scoring
   - write result JSON
4. Aggregate completed tasks into `summary.json`.
5. Optionally compare runs or export a submission.

## Design Constraints

- Prefer preserving working runtime paths over aggressive refactors.
- Keep each failed run inspectable via task-level JSON and persisted artifacts.
- Bias toward exact-match-friendly answers rather than verbose reasoning output.
- Isolate environment loading and persistence so benchmark reruns remain reproducible.
- Follow the repo convention that structured data contracts should live in `basemodels.py`
  when practical, mirroring the explicit workflow-contract style used in `cadence-backend`.
