from __future__ import annotations

import json
from pathlib import Path

from gaia_bot.benchmark.results import load_task_results
from gaia_bot.config.settings import load_settings
from gaia_bot.contracts.basemodels import SubmissionRow


def export_submission(run_id: str, output: str | None = None) -> Path:
    settings = load_settings()
    run_dir = settings.results_dir / run_id
    results = load_task_results(run_dir)
    destination = Path(output) if output else run_dir / "submission.jsonl"
    with destination.open("w") as handle:
        for result in results:
            row = SubmissionRow(
                task_id=result.task_id,
                model_answer=result.scorer_answer or result.answer,
                reasoning_trace=result.solver.reasoning_summary or None,
            )
            handle.write(json.dumps(row.model_dump(), ensure_ascii=True) + "\n")
    return destination


__all__ = ["export_submission"]
