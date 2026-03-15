# Repo Layout

## Top Level

- `README.md`
  - project overview, quick start, benchmark commands
- `AGENTS.md`
  - repo-level coding conventions and agent instructions
- `CLAUDE.md`
  - repo instructions for Claude Code or similar coding agents
- `pyproject.toml`
  - package metadata, dependencies, lint and test configuration
- `.env.example`
  - expected environment variable shape
- `docs/`
  - supporting documentation and runbooks
- `skills/`
  - repo-local workflow skills
- `src/gaia_bot/`
  - application code
- `tests/`
  - unit and integration tests
- `artifacts/conversations/`
  - tracked placeholder for exported conversation logs
- `artifacts/results/`
  - ignored benchmark run outputs

## Source Package

- `agent.py`
  - solve loop and Claude Agent SDK integration
- `artifacts.py`
  - task attachment extraction and persistence
- `benchmark.py`
  - dataset loading and subset selection
- `compare_runs.py`
  - run diff CLI
- `eval.py`
  - evaluation CLI and parallel runner
- `executor.py`
  - E2B sandbox execution wrapper
- `export_submission.py`
  - submission JSONL export CLI
- `basemodels.py`
  - structured pydantic contracts for tasks, traces, and results
- `models.py`
  - compatibility re-export for older imports
- `prompts.py`
  - system, routing, solving, verifier prompts
- `research.py`
  - web search and fetch helpers
- `results.py`
  - run directory, task results, summaries, comparisons
- `router.py`
  - heuristic task routing
- `run.py`
  - single-task CLI
- `scoring.py`
  - answer normalization and exact-match scoring
- `settings.py`
  - settings and dotenv validation
- `smoke.py`
  - live smoke test CLI

## Test Layout

- `tests/test_*.py`
  - unit tests for scoring, routing, artifacts, executor, results, and settings
- `tests/integration/test_services.py`
  - live service integration test
- `tests/fixtures/`
  - benchmark-style local fixtures

## Documentation Layout

- `docs/architecture.md`
- `docs/benchmarking.md`
- `docs/repo-layout.md`
- `docs/submission-checklist.md`

## Skills Layout

- `skills/README.md`
- `skills/gaia-benchmark-ops/SKILL.md`
- `skills/gaia-failure-triage/SKILL.md`
