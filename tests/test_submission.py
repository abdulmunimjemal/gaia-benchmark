from __future__ import annotations

import json
from datetime import UTC, datetime

from gaia_bot.export_submission import export_submission
from gaia_bot.models import JudgeOutput, PlannerDecision, SolverOutput, TaskRunResult
from gaia_bot.results import ensure_run_directory, write_task_result


def test_export_submission_writes_jsonl(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    run_dir = ensure_run_directory(tmp_path, "run-1")
    result = TaskRunResult(
        run_id="run-1",
        task_id="sample-1",
        question="What is 2 + 2?",
        answer="4",
        scorer_answer="4",
        expected_answer="4",
        score=1.0,
        passed=True,
        planner=PlannerDecision(route="direct", risk="low", use_verifier=False),
        solver=SolverOutput(answer="4", confidence="high", reasoning_summary="simple"),
        judge=JudgeOutput(is_sufficient=True, issues=[], revised_answer="4"),
        duration_seconds=0.2,
        created_at=datetime(2026, 3, 14, tzinfo=UTC),
    )
    write_task_result(run_dir, result)

    output = export_submission("run-1")
    lines = output.read_text().splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["model_answer"] == "4"
