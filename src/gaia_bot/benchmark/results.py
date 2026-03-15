from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia_bot.benchmark.scoring import score_breakdown
from gaia_bot.contracts.basemodels import TaskRunResult


def create_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return now.strftime("%Y%m%dT%H%M%S%fZ")


def ensure_run_directory(base_dir: Path, run_id: str) -> Path:
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def task_workspace(run_dir: Path, task_id: str) -> Path:
    workspace = run_dir / "_artifacts" / task_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def write_run_manifest(run_dir: Path, manifest: dict[str, Any]) -> Path:
    destination = run_dir / "manifest.json"
    payload = {"created_at": datetime.now(UTC).isoformat(), **manifest}
    destination.write_text(json.dumps(payload, indent=2))
    return destination


def write_task_result(run_dir: Path, result: TaskRunResult) -> Path:
    destination = run_dir / f"{result.task_id}.json"
    destination.write_text(result.model_dump_json(indent=2))
    return destination


def load_task_results(run_dir: Path) -> list[TaskRunResult]:
    results: list[TaskRunResult] = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {"summary.json", "manifest.json"}:
            continue
        results.append(TaskRunResult.model_validate_json(path.read_text()))
    return results


def completed_task_ids(run_dir: Path) -> set[str]:
    return {result.task_id for result in load_task_results(run_dir)}


def write_summary(run_dir: Path, results: list[TaskRunResult]) -> Path:
    scored = [result for result in results if result.score is not None]
    breakdown = score_breakdown(results)
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
        "avg_duration_seconds": (
            sum(item.duration_seconds for item in results) / len(results)
            if results
            else None
        ),
        "avg_retry_count": (
            sum(item.retry_count for item in results) / len(results)
            if results
            else None
        ),
        **breakdown,
        "created_at": datetime.now(UTC).isoformat(),
    }
    destination = run_dir / "summary.json"
    destination.write_text(json.dumps(summary, indent=2))
    return destination


__all__ = [
    "completed_task_ids",
    "create_run_id",
    "ensure_run_directory",
    "load_task_results",
    "task_workspace",
    "write_run_manifest",
    "write_summary",
    "write_task_result",
]
