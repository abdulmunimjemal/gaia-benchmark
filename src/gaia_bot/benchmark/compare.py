from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia_bot.benchmark.results import load_task_results


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


__all__ = ["compare_run_directories"]
