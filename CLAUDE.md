# CLAUDE.md

Repository instructions for Claude Code or other coding agents working in this project.

## Objective

The primary goal of this repository is benchmark performance on GAIA with reproducible runs, not generic chatbot quality.

Priorities, in order:

1. exact benchmark correctness
2. stable end-to-end execution against the real dataset
3. fast failure analysis and reruns
4. readable submission artifacts

## Environment

Use:

- Python `3.14.2`
- `uv`
- live credentials from `.env`
- `claude` CLI on `PATH`

Verify before major changes:

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
uv run --python 3.14.2 ruff check .
uv run --python 3.14.2 pytest
```

## Benchmark Rules

- Prefer official GAIA data via `hf://gaia-benchmark/GAIA?...`.
- Always include a GAIA config name such as `2023_all`.
- For expensive runs, start with a subset and compare runs before using `--full`.
- Treat interrupted runs carefully; confirm whether a run directory contains real task results or only failure placeholders.
- Do not trust a benchmark score unless the run directory contains real per-task outputs with tool traces or meaningful solver output.

## Code Organization

Adopted from the stronger conventions in `cadence-backend`:

- structured contracts belong in `src/gaia_bot/contracts/basemodels.py`
- `src/gaia_bot/models.py` is a compatibility re-export layer
- settings live in `src/gaia_bot/config/settings.py`
- when a module grows into a multi-part workflow unit, prefer splitting it into:
  - `main.py`
  - `basemodels.py`
  - `constants.py`
  - `states.py`
- keep explicit exports in public-facing `__init__.py` files

Current package layout:

- `src/gaia_bot/agent/`
- `src/gaia_bot/benchmark/`
- `src/gaia_bot/services/`
- `src/gaia_bot/routing/`
- `src/gaia_bot/prompts/`
- `src/gaia_bot/config/`
- `src/gaia_bot/contracts/`
- `src/gaia_bot/cli/`

## Debugging Norms

- When explaining a bug or proposing a fix, use dry-run examples when they make the issue clearer.
- Separate formatting misses from retrieval misses and runtime failures.
- If a task depends on counting, sorting, comparison, coordinates, or unit conversion, bias toward web-plus-code instead of pure web synthesis.
- If a task includes an attachment, avoid routing it through unnecessary planner steps before reading the attachment.

## Result Hygiene

- Keep benchmark outputs under `artifacts/results/`.
- Keep Claude Code exports under `artifacts/conversations/`.
- Do not commit secrets, run outputs, or local caches.
- Preserve failed run directories when they are useful for debugging, but summarize their real meaning in docs or commit messages.

## Repo-Specific Skills

Use the repo-local skills in [skills/README.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/skills/README.md):

- `gaia-benchmark-ops`
- `gaia-failure-triage`

## Preferred Workflow

1. Reproduce on a single task or a small subset.
2. Inspect the task result JSON and artifact extracts.
3. Patch the narrowest failure mode.
4. Re-run targeted validation.
5. Only then escalate to broader benchmark runs.
