# Repo Layout

Docs: [Index](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/README.md)
Previous: [docs/architecture.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/architecture.md)
Next: [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)

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

- `agent/`
  - agent orchestration and Claude Agent SDK integration
  - `main.py`
    - `GaiaAgent`, verification flow, answer finalization
  - `runtime.py`
    - MCP runtime, tool registration, and trace capture
  - `constants.py`
    - runtime-level tool and prompt defaults
  - `basemodels.py`
    - agent-scoped contracts if needed beyond shared contracts
- `benchmark/`
  - evaluation and scoring package
  - `dataset.py`
    - dataset loading and subset selection
  - `scoring.py`
    - answer normalization and exact-match scoring
  - `results.py`
    - run directories, per-task outputs, and summaries
  - `submission.py`
    - leaderboard JSONL export helpers
  - `compare.py`
    - run diff helpers
- `compare_runs.py`
  - compatibility shim for `python -m gaia_bot.compare_runs`
- `eval.py`
  - compatibility shim for `python -m gaia_bot.eval`
- `export_submission.py`
  - compatibility shim for `python -m gaia_bot.export_submission`
- `models.py`
  - compatibility re-export for shared contracts
- `run.py`
  - compatibility shim for `python -m gaia_bot.run`
- `settings.py`
  - compatibility re-export for config loading
- `smoke.py`
  - compatibility shim for `python -m gaia_bot.smoke`
- `cli/`
  - console script implementations
- `config/`
  - settings and dotenv validation
- `contracts/`
  - structured pydantic contracts for tasks, traces, and results
- `prompts/`
  - system, routing, solving, and verifier prompt builders/constants
- `routing/`
  - heuristic task routing and route constants
- `services/`
  - E2B sandbox execution, web research, and artifact extraction

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

Previous: [docs/architecture.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/architecture.md)
Next: [docs/benchmarking.md](/Users/abdulmunimjundurahman/work/upwork/gaia-bot/docs/benchmarking.md)
