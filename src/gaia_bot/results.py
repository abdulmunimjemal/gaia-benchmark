from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia_bot.models import TaskRunResult
from gaia_bot.scoring import score_breakdown


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


def compare_run_directories(base_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    base = {result.task_id: result for result in load_task_results(base_dir)}
    candidate = {result.task_id: result for result in load_task_results(candidate_dir)}
    all_ids = sorted(set(base) | set(candidate))

    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []

    for task_id in all_ids:
        base_score = base.get(task_id).score if task_id in base else None
        candidate_score = candidate.get(task_id).score if task_id in candidate else None
        if base_score is None or candidate_score is None:
            unchanged.append(task_id)
        elif candidate_score > base_score:
            improved.append(task_id)
        elif candidate_score < base_score:
            regressed.append(task_id)
        else:
            unchanged.append(task_id)

    base_average = _average_score(base.values()) or 0.0
    candidate_average = _average_score(candidate.values()) or 0.0
    return {
        "base_run": base_dir.name,
        "candidate_run": candidate_dir.name,
        "base_average_score": base_average,
        "candidate_average_score": candidate_average,
        "score_delta": candidate_average - base_average,
        "improved_tasks": improved,
        "regressed_tasks": regressed,
        "unchanged_tasks": unchanged,
    }


def _average_score(results: Any) -> float | None:
    scored = [item.score for item in results if item.score is not None]
    if not scored:
        return None
    return sum(scored) / len(scored)
