# gaia-failure-triage

Use this skill when a GAIA task or evaluation run is failing, timing out, or scoring incorrectly.

## Goal

Turn a benchmark miss into a concrete diagnosis and the smallest defensible fix.

## Workflow

1. Inspect the failing task JSON in `artifacts/results/<run-id>/<task-id>.json`.
2. Pull the exact task question and expected answer from the dataset if needed.
3. Classify the failure:
   - formatting miss
   - wrong answer
   - retrieval miss
   - parsing miss
   - runtime / transport failure
4. Inspect `_artifacts/<task-id>/` for fetched pages or extracted files.
5. Use dry-run examples when explaining the bug.
6. Patch the narrowest layer responsible:
   - `scoring.py` for formatting
   - `router.py` for route choice
   - `prompts.py` for benchmark guidance
   - `research.py` for search/fetch issues
   - `artifacts.py` for attachment extraction
   - `agent.py` / `eval.py` for runtime control flow
7. Re-run the failing task or a small subset before escalating.

## Useful Commands

Single task replay:

```bash
uv run --python 3.14.2 python -m gaia_bot.run --task-id <task-id> --dataset '<dataset>'
```

Targeted tests:

```bash
uv run --python 3.14.2 pytest tests/test_router.py tests/test_scoring.py
```

Full local verification:

```bash
uv run --python 3.14.2 ruff check .
uv run --python 3.14.2 pytest
```

## Guardrails

- Do not jump straight to a full benchmark rerun after an unverified patch.
- Keep explanations concrete. Prefer “expected X, predicted Y” over generic descriptions.
- Distinguish solver failure from scorer failure before changing prompts.
