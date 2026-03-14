from __future__ import annotations

from gaia_bot.benchmark import load_tasks, score_prediction, select_subset


def test_load_tasks_from_jsonl(sample_dataset_path) -> None:
    tasks = load_tasks(sample_dataset_path)

    assert len(tasks) == 4
    assert tasks[0].task_id == "sample-1"
    assert tasks[0].question == "What is 2 + 2?"


def test_score_prediction_normalizes_whitespace_and_case() -> None:
    assert score_prediction("  paris ", "Paris") == 1.0
    assert score_prediction("Lyon", "Paris") == 0.0


def test_select_subset_by_count(sample_dataset_path) -> None:
    tasks = load_tasks(sample_dataset_path)

    selected = select_subset(tasks, 2)

    assert [task.task_id for task in selected] == ["sample-1", "sample-2"]
