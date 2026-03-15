# gaia-benchmark-ops

Use this skill when the task is about running or packaging GAIA benchmark evaluations.

## Goal

Operate the benchmark harness consistently without confusing interrupted runs, partial runs, and real scored outputs.

## Workflow

1. Verify credentials and local readiness.
2. Confirm the target dataset URI and subset.
3. Start with smoke or a small subset unless the user explicitly wants a broad run.
4. Inspect the run directory while the benchmark is executing.
5. After completion, summarize:
   - completed tasks
   - correct tasks
   - partial accuracy if incomplete
   - whether the run is meaningful or was interrupted
6. If requested, export `submission.jsonl`.

## Commands

Smoke:

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
```

Subset:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --dataset '<dataset>' --subset 6 --parallel 3
```

Full:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --dataset '<dataset>' --full --parallel 3
```

Compare:

```bash
uv run --python 3.14.2 python -m gaia_bot.compare_runs --base <run-id> --candidate <run-id>
```

Export:

```bash
uv run --python 3.14.2 python -m gaia_bot.export_submission --run-id <run-id>
```

## Guardrails

- Do not report a run as valid if it only contains placeholder failures.
- Always inspect task JSON files, not just terminal output.
- If the run was interrupted, say so explicitly and report the last meaningful partial result instead.
