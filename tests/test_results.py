from __future__ import annotations

from datetime import UTC, datetime

from gaia_bot.models import JudgeOutput, PlannerDecision, SolverOutput, TaskRunResult
from gaia_bot.results import create_run_id, ensure_run_directory, write_summary, write_task_result


def test_write_result_and_summary(tmp_path) -> None:
    run_id = create_run_id(datetime(2026, 3, 14, 12, 0, tzinfo=UTC))
    run_dir = ensure_run_directory(tmp_path, run_id)
    result = TaskRunResult(
        run_id=run_id,
        task_id="sample-1",
        question="What is 2 + 2?",
        answer="4",
        expected_answer="4",
        score=1.0,
        passed=True,
        planner=PlannerDecision(
            needs_code=True,
            working_plan=["Use sandbox"],
            answer_shape="number",
        ),
        solver=SolverOutput(
            answer="4",
            confidence="high",
            citations=["sandbox"],
            reasoning_summary="Simple arithmetic",
        ),
        judge=JudgeOutput(is_sufficient=True, issues=[]),
        duration_seconds=0.5,
    )

    task_path = write_task_result(run_dir, result)
    summary_path = write_summary(run_dir, [result])

    assert task_path.exists()
    assert summary_path.exists()
    assert '"average_score": 1.0' in summary_path.read_text()
