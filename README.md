# GAIA Bot Baseline

GAIA benchmark baseline built on Anthropic's Claude Agent SDK and E2B sandboxes.

## Requirements

- Python `3.14.2` via `uv`
- `claude` CLI available on `PATH`
- Valid `ANTHROPIC_API_KEY`
- Valid `E2B_API_KEY`

## Setup

```bash
uv python install 3.14.2
uv sync --python 3.14.2 --extra dev
cp .env.example .env
```

The current broken `.env` shape is a raw secret value on its own:

```dotenv
sk-ant-...
```

The required shape is explicit `KEY=value` pairs:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
E2B_API_KEY=e2b_...
```

## Commands

Smoke test Anthropic + Claude Agent SDK + E2B:

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
```

Run a single task:

```bash
uv run --python 3.14.2 python -m gaia_bot.run --task-id sample-1
```

Run a subset:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --subset 5
```

Run the full dataset:

```bash
uv run --python 3.14.2 python -m gaia_bot.eval --full
```

The dataset loader accepts:

- Local JSON / JSONL files via `GAIA_DATA_PATH=/abs/path/tasks.jsonl`
- Hugging Face datasets via `GAIA_DATA_PATH=hf://gaia-benchmark/GAIA?split=validation`

## Output Layout

Results are written to `RESULTS_DIR` under a timestamped run directory:

- `summary.json`
- `<task-id>.json`

Each task result contains the prompt, answer, score, timing, planner output, tool calls, and judge notes.

## Git Milestones

Suggested commit sequence for the paid-trial submission:

1. Bootstrap project metadata and settings validation.
2. Add E2B executor and research tools.
3. Add Claude Agent SDK pipeline and CLIs.
4. Add GAIA loader, scorer, and result persistence.
5. Add tests and benchmark artifacts.

## Claude Code Transcript Export

Store exported Claude Code conversation logs under `artifacts/conversations/` before submission. A placeholder README lives there so the folder is tracked even before the export is added.
