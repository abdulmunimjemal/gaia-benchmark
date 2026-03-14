# Benchmarking

Docs: [Index](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Previous: [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
Next: [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md)

## Dataset URIs

Preferred GAIA dataset URI shape:

```bash
hf://gaia-benchmark/GAIA?split=validation&subset=2023_all
```

Common configs:

- `2023_all`
- `2023_level1`
- `2023_level2`
- `2023_level3`

## Recommended Evaluation Flow

### 1. Smoke test

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
```

This should verify:

- Anthropic API access
- Claude Agent SDK wiring
- E2B sandbox execution

### 2. Reproduce a single task

```bash
uv run --python 3.14.2 python -m gaia_bot.run \
  --task-id <task-id> \
  --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all'
```

Use this for:

- routing bugs
- formatting misses
- runtime failures
- attachment parsing regressions

### 3. Run a subset

```bash
uv run --python 3.14.2 python -m gaia_bot.eval \
  --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all' \
  --subset 6 \
  --parallel 3
```

Use subset runs to validate:

- solve throughput
- route mix
- failure taxonomy
- score direction after prompt or runtime changes

### 4. Compare runs

```bash
uv run --python 3.14.2 python -m gaia_bot.compare_runs \
  --base <run-id> \
  --candidate <run-id>
```

Use this before scaling to broader runs.

### 5. Run full validation

```bash
uv run --python 3.14.2 python -m gaia_bot.eval \
  --dataset 'hf://gaia-benchmark/GAIA?split=validation&subset=2023_all' \
  --full \
  --parallel 3
```

## Run Directory Semantics

Each run directory under `artifacts/results/` can contain:

- `manifest.json`
- `summary.json`
- one `<task-id>.json` file per completed task
- `_artifacts/<task-id>/...` extracts fetched or parsed during the solve

Interpretation rules:

- if a run has only `manifest.json`, it never produced useful task results
- if a run has task JSON files with empty answers and zero durations, treat it as a failed or interrupted run, not a meaningful benchmark score
- partial runs can still be useful for debugging if they contain solver output, tool traces, or persisted artifacts

## Synthetic Preview Run

Current synthetic preview run:

- run id: `20260315T041323853151Z`
- directory: `artifacts/results/20260315T041323853151Z/`
- tasks: `40`
- accuracy: `0.575` (`23/40`)

This run is intentionally synthetic and is marked with `synthetic: true` in each task result and in `manifest.json` and `summary.json`. It is useful for checking artifact structure and repo output shape, not for leaderboard claims.

## Common Failure Modes

### Formatting miss

Example:

- expected: `A Nightmare on Elm Street`
- predicted: `Nightmare on Elm Street`

Fix in:

- `src/gaia_bot/benchmark/scoring.py`
- `src/gaia_bot/prompts/`

### Runtime or transport failure

Example symptoms:

- `CLIConnectionError`
- `ProcessTransport is not ready for writing`
- empty task result with `tool_failure`

Fix in:

- `src/gaia_bot/agent/main.py`
- `src/gaia_bot/cli/eval.py`

### Attachment routing failure

Example:

- attachment task times out before the file is even parsed

Fix in:

- `src/gaia_bot/routing/main.py`
- `src/gaia_bot/agent/main.py`
- `src/gaia_bot/services/artifacts.py`

## Submission Export

After choosing a run:

```bash
uv run --python 3.14.2 python -m gaia_bot.export_submission --run-id <run-id>
```

This writes `submission.jsonl` into the selected run directory unless `--output` is provided.

Previous: [docs/repo-layout.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/repo-layout.md)
Next: [docs/submission-checklist.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/submission-checklist.md)
