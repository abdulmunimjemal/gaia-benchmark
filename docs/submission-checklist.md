# Submission Checklist

Docs: [Index](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Previous: [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
Next: [README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/README.md)

Use this before packaging the paid-trial handoff.

## Code and History

- repository is committed with meaningful grouped commits
- working tree is clean
- `README.md` reflects the current workflow
- `CLAUDE.md` reflects repo-specific instructions

## Verification

- `uv run --python 3.14.2 ruff check .`
- `uv run --python 3.14.2 pytest`
- `uv run --python 3.14.2 python -m gaia_bot.smoke`

Record any failures or skipped checks explicitly if credentials or live services are unavailable.

## Benchmark Outputs

- chosen run directory exists under `artifacts/results/<run-id>/`
- `summary.json` exists for the chosen run
- task result JSON files are present and look meaningful
- no placeholder-only interrupted run is being used as the benchmark report
- `submission.jsonl` has been generated from the chosen run

## Trial Artifacts

- benchmark results captured
- exported Claude Code conversations stored under `artifacts/conversations/`
- git history preserved
- run id for the chosen submission recorded in notes or handoff message

## Optional but Useful

- run comparison against a prior baseline
- short note on known failure modes still being worked
- partial validation statistics if the full run is not yet stable

Previous: [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
Next: [README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/README.md)
