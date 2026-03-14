# Architecture

Docs: [Index](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Previous: [docs/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Next: [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)

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

- `src/gaia_bot/config/settings.py`
  - environment loading, validation, runtime defaults
- `src/gaia_bot/cli/smoke.py`
  - live connectivity checks
- `src/gaia_bot/cli/run.py`
  - single-task execution
- `src/gaia_bot/cli/eval.py`
  - subset or full benchmark evaluation
- `src/gaia_bot/cli/export_submission.py`
  - submission JSONL export
- `src/gaia_bot/cli/compare_runs.py`
  - run-to-run comparison
- `src/gaia_bot/smoke.py`, `run.py`, `eval.py`, `export_submission.py`, `compare_runs.py`
  - compatibility shims for `python -m gaia_bot.<command>`

### Agent runtime

- `src/gaia_bot/agent/main.py`
  - main solve loop
  - route selection
  - Claude Agent SDK structured query calls
  - verifier pass
  - runtime MCP tool exposure
- `src/gaia_bot/agent/runtime.py`
  - MCP tool registration and sandbox-backed runtime operations
- `src/gaia_bot/agent/constants.py`
  - runtime defaults and allowed tool names
- `src/gaia_bot/prompts/`
  - benchmark-specific system and task prompt builders
- `src/gaia_bot/routing/main.py`
  - heuristic task routing

### Retrieval and execution

- `src/gaia_bot/services/research.py`
  - web search and fetch helpers
- `src/gaia_bot/services/artifacts.py`
  - attachment and local-file extraction
- `src/gaia_bot/services/executor.py`
  - E2B sandbox wrapper

### Benchmark data and persistence

- `src/gaia_bot/benchmark/dataset.py`
  - local and Hugging Face dataset loading
- `src/gaia_bot/contracts/basemodels.py`
  - structured pydantic contracts for task, solver, trace, and submission data
- `src/gaia_bot/benchmark/scoring.py`
  - answer extraction, formatting, and exact-match scoring
- `src/gaia_bot/benchmark/results.py`
  - run directory creation, task result writes, and summaries
- `src/gaia_bot/benchmark/compare.py`
  - run comparisons
- `src/gaia_bot/benchmark/submission.py`
  - leaderboard export helpers
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
- Follow the repo convention that shared structured data contracts should live in
  `contracts/basemodels.py`, mirroring the explicit workflow-contract style used in
  `cadence-backend`.

Previous: [docs/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Next: [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
