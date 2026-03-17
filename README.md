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

## Current Results

Full validation run on `2023_all` (165 tasks):

- **Run ID:** `20260316T214520230195Z`
- **Score:** 86/165 (52.1%)
- **Avg duration:** 291s/task
- **Total tool calls:** 2,359

### Pass Rate by Route

| Route | Passed | Total | Rate |
|-------|--------|-------|------|
| direct | 3 | 4 | 75.0% |
| web | 47 | 79 | 59.5% |
| code | 20 | 44 | 45.5% |
| artifact | 14 | 38 | 36.8% |

### Failure Analysis (79 failures)

| Category | Count | Description |
|----------|-------|-------------|
| Wrong answer | 60 | Reasoning, calculation, or factual errors |
| Multimodal (unsupported) | 16 | Audio, video, and image tasks the agent cannot process |
| Tool failure | 7 | Runtime crashes (sandbox 502, stream closed, TaskGroup errors) |
| Retrieval miss | 4 | Retrieved wrong source or outdated information |

#### Multimodal Limitations (16 tasks)

The GAIA benchmark includes tasks that require processing audio, video, and image content. Our agent pipeline is **text-only** — it uses web search, URL fetching, and E2B code execution, but has no native multimodal perception. These 16 tasks are expected failures:

- **Video (6 tasks):** Questions referencing YouTube videos, requiring watching specific timestamps or identifying visual content. Example: *"At the two-minute mark in the YouTube video uploaded by GameGrumps..."*
- **Image (7 tasks):** Questions requiring reading charts, chess positions, screenshots, or visual puzzles. Example: *"Review the chess position provided in the image..."*
- **Audio (3 tasks):** Questions requiring listening to MP3 recordings or identifying spoken content. Example: *"I was out sick from my classes on Friday, so I'm trying to figure out what I missed from the audio recording..."*

Without multimodal support, these tasks receive either a best-effort answer from web context or a fallback from model knowledge. Adding vision (via Claude's multimodal API) and audio transcription (via Whisper or similar) would recover an estimated 8-12 of these tasks.

#### Tool and Runtime Failures (7 tasks)

These tasks failed due to infrastructure issues, not reasoning:

- **Sandbox crashes (3):** E2B sandbox returned 502 or "sandbox not found" mid-execution. The agent now auto-recreates sandboxes on failure, but some tasks hit the retry limit.
- **CancelledError / timeout (2):** Tasks exceeded the 12-minute hard limit, typically on complex multi-step research requiring many sequential tool calls.
- **Stream disconnects (2):** The Claude CLI subprocess lost its connection mid-query. Retry logic now handles this, but concurrent load can still trigger it.

#### Wrong Answers (60 tasks)

The largest failure category. Common patterns:

- **Close but not exact (12):** Agent retrieved the right entity but got a detail wrong — e.g., wrong name in a pair, off-by-one in a count, wrong date format.
- **Outdated or wrong source (15):** Agent used a secondary source instead of the authoritative one, or confused similar entities (e.g., wrong NASA grant number, wrong Wikipedia revision date).
- **Complex multi-hop reasoning (18):** Tasks requiring 4+ steps of chained reasoning where the agent lost track or made an error in an intermediate step.
- **Calculation / counting errors (8):** Numerical tasks where the agent's code execution produced an incorrect result or the agent didn't use code when it should have.
- **Artifact parsing gaps (7):** PDF or spreadsheet content was partially extracted, leading to incomplete data for the answer.

## Documentation Index

Recommended flow:

1. [docs/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
2. [docs/architecture.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/architecture.md)
3. [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
4. [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
5. [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md)

Supporting docs:

- [CLAUDE.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/CLAUDE.md)
- [AGENTS.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/AGENTS.md)
- [docs/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
- [docs/architecture.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/architecture.md)
- [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
- [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
- [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md)
- [skills/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/skills/README.md)

## Verification

Primary verification commands:

```bash
uv run --python 3.14.2 ruff check .
uv run --python 3.14.2 pytest
```
