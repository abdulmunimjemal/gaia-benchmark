# Agents Guide

GAIA Bot: benchmark-focused agent runtime for GAIA evaluation with Anthropic's Claude Agent SDK and E2B.

This file captures repo conventions that coding agents should follow when changing this project.

## Project Layout

Key directories and files:

- `src/gaia_bot/`
  - core runtime, routing, scoring, benchmark CLIs, and persistence
- `tests/`
  - unit and integration regression coverage
- `docs/`
  - architecture notes, runbooks, and submission checklist
- `skills/`
  - repo-local workflow skills
- `artifacts/conversations/`
  - exported Claude Code conversations for submission
- `AGENTS.md`
  - coding standards and repo-specific agent instructions
- `CLAUDE.md`
  - condensed repository instructions for Claude Code workflows

## Architecture Convention

Borrowing the strongest convention from `cadence-backend`, keep contracts and prompts close to the workflow unit they support.

Current guidance for this repo:

- shared structured data contracts belong in `src/gaia_bot/contracts/basemodels.py`
- prompts and hardcoded benchmark instructions belong in `src/gaia_bot/prompts/`
- routing rules belong in `src/gaia_bot/routing/`
- scoring and run persistence belong in `src/gaia_bot/benchmark/`
- artifact parsing and service adapters belong in `src/gaia_bot/services/`
- CLI implementations belong in `src/gaia_bot/cli/`

If a module grows significantly, prefer splitting it into:

- `main.py`
- `basemodels.py`
- `constants.py`
- `states.py`

Only do that when the file is genuinely becoming multi-purpose.

Top-level compatibility entrypoints at `src/gaia_bot/*.py` are intentionally thin shims for
`python -m gaia_bot.<command>`. Do not put real logic there.

## Coding Best Practices

- Use Python `3.14.2` syntax with full type hints.
- Follow existing style: absolute imports, `ruff`, 100-char lines.
- Keep public functions above private helpers where practical.
- Prefer small functions with explicit names.
- Add docstrings to new public functions and non-trivial helpers.
- Use explicit `__all__` where a module is acting as a public surface.
- Keep benchmark-facing prompts deterministic and exact-match-oriented.

## Error Handling

- Let low-level exceptions bubble until a meaningful boundary exists.
- Catch and re-wrap only at workflow or runner boundaries where the run result needs to be persisted.
- Separate these failure classes in reasoning and fixes:
  - formatting miss
  - wrong answer
  - retrieval miss
  - parsing miss
  - runtime / transport failure

## Benchmark Workflow

- Start with `smoke`, then a single task, then a subset, then full evaluation.
- Do not trust interrupted runs without inspecting per-task JSON files.
- Prefer comparing runs before claiming improvement.
- Use dry-run examples when describing benchmark failures and fixes.

## Verification

Run before finishing a meaningful change:

```bash
uv run --python 3.14.2 ruff check .
uv run --python 3.14.2 pytest
```

For live-service-impacting changes, also run:

```bash
uv run --python 3.14.2 python -m gaia_bot.smoke
```

## Notes for AI Agents

- Reuse existing benchmark utilities before adding new abstractions.
- Avoid large structural refactors while the benchmark path is unstable.
- Update docs when repo structure or workflow conventions change.
- Prefer meaningful grouped commits.
