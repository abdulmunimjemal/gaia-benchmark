from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from gaia_bot.models import TaskRunResult


def create_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y%m%dT%H%M%SZ")


def ensure_run_directory(base_dir: Path, run_id: str) -> Path:
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_task_result(run_dir: Path, result: TaskRunResult) -> Path:
    destination = run_dir / f"{result.task_id}.json"
    destination.write_text(result.model_dump_json(indent=2))
    return destination


def write_summary(run_dir: Path, results: list[TaskRunResult]) -> Path:
    scored = [result for result in results if result.score is not None]
    summary = {
        "total_tasks": len(results),
        "scored_tasks": len(scored),
        "average_score": (
            sum(item.score or 0.0 for item in scored) / len(scored)
            if scored
            else None
        ),
        "passed_tasks": sum(1 for item in scored if item.passed),
        "task_ids": [item.task_id for item in results],
        "created_at": datetime.now(UTC).isoformat(),
    }
    destination = run_dir / "summary.json"
    destination.write_text(json.dumps(summary, indent=2))
    return destination
