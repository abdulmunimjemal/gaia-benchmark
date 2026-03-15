# GAIA Bot

GAIA benchmark agent built on Anthropic's Claude Agent SDK, E2B sandboxes, and a reproducible evaluation harness.

This repository is organized for three things:

- benchmark iteration against GAIA
- debugging and replaying failures quickly
- producing trial-submission artifacts cleanly

## Quick Start

Requirements:

- Python `3.14.2`
- `uv`
- `claude` CLI on `PATH`
- valid `ANTHROPIC_API_KEY`
- valid `E2B_API_KEY`
- optional `HF_TOKEN` for gated Hugging Face access

Install and sync:

```bash
uv python install 3.14.2
uv sync --python 3.14.2 --extra dev
cp .env.example .env
```

The `.env` file must use explicit `KEY=value` pairs:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
E2B_API_KEY=e2b_...
HF_TOKEN=hf_...
GAIA_DATA_PATH=hf://gaia-benchmark/GAIA?split=validation&subset=2023_all
```

If a raw secret is pasted on its own line, settings validation fails fast instead of silently misconfiguring the run.

## Core Commands

Use the module commands directly, or the console entry points after `uv sync`.

Smoke test live services:

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
```

Run one task:

```bash
uv run --python 3.14.2 python -m gaia_bot.run --task-id <task-id> --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all'
```

Run a subset in parallel:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all' --subset 6 --parallel 3
```

Run a full validation pass:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all' --full --parallel 3
```

Export a leaderboard-style submission artifact:

```bash
uv run --python 3.14.2 python -m gaia_bot.export_submission --run-id <run-id>
```

Compare two runs:

```bash
uv run --python 3.14.2 python -m gaia_bot.compare_runs --base <run-id> --candidate <run-id>
```

Equivalent console entry points:

- `gaia-smoke`
- `gaia-run`
- `gaia-eval`
- `gaia-export`
- `gaia-compare`

## Dataset Formats

`GAIA_DATA_PATH` accepts:

- local `json` / `jsonl`
- Hugging Face dataset URIs like `hf://gaia-benchmark/GAIA?split=validation&subset=2023_all`

For GAIA on Hugging Face, a config name is required. Valid benchmark configs include:

- `2023_all`
- `2023_level1`
- `2023_level2`
- `2023_level3`

## Repository Layout

Top-level structure:

- `src/gaia_bot/`
  - modular runtime packages, benchmark logic, and compatibility entrypoints
- `tests/`
  - unit and integration coverage
- `docs/`
  - architecture, benchmarking workflow, repo layout, submission checklist
- `skills/`
  - repo-local workflow skills for benchmark operations and failure triage
- `artifacts/conversations/`
  - exported Claude Code conversation history for submission
- `artifacts/results/`
  - ignored run outputs and benchmark artifacts

See [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md) for a more detailed map.

Primary source packages:

- `src/gaia_bot/agent/`
  - agent orchestration, runtime wiring, and agent-scoped constants
- `src/gaia_bot/benchmark/`
  - dataset loading, scoring, results, submission export, and run comparison
- `src/gaia_bot/services/`
  - E2B execution, web research, and artifact extraction
- `src/gaia_bot/routing/`
  - heuristic route selection and routing constants
- `src/gaia_bot/prompts/`
  - benchmark prompt builders and prompt constants
- `src/gaia_bot/config/`
  - typed settings and dotenv validation
- `src/gaia_bot/contracts/`
  - shared pydantic contracts
- `src/gaia_bot/cli/`
  - console entrypoints

Compatibility shims remain at the package root for:

- `python -m gaia_bot.smoke`
- `python -m gaia_bot.run`
- `python -m gaia_bot.eval`
- `python -m gaia_bot.export_submission`
- `python -m gaia_bot.compare_runs`

## Benchmark Workflow

Recommended loop:

1. `python -m gaia_bot.smoke` to verify Anthropic, Claude Agent SDK, and E2B.
2. `python -m gaia_bot.run` on a single failing task while iterating on prompts or routing.
3. `python -m gaia_bot.eval --subset ... --parallel 3` for fast benchmark feedback.
4. `python -m gaia_bot.compare_runs` to measure deltas before broader runs.
5. `python -m gaia_bot.eval --full` only after subset behavior is stable.
6. `python -m gaia_bot.export_submission` once a run is worth packaging.

See [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md) for the detailed runbook.

## Documentation Index

- [CLAUDE.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/CLAUDE.md)
- [AGENTS.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/AGENTS.md)
- [docs/architecture.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/architecture.md)
- [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
- [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
- [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md)
- [skills/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/skills/README.md)

## Verification

Primary verification commands:

```bash
uv run --python 3.14.2 ruff check .
uv run --python 3.14.2 pytest
```

## Submission Artifacts

For the paid-trial handoff, the repository should be accompanied by:

- benchmark run directories or exported results
- git history
- exported Claude Code conversations under `artifacts/conversations/`
- submission JSONL generated from a selected run

Use [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md) as the final handoff checklist.
