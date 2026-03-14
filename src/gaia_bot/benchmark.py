from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from datasets import load_dataset
from huggingface_hub import snapshot_download

from gaia_bot.models import TaskRecord
from gaia_bot.scoring import score_prediction


def _task_from_mapping(payload: dict, *, dataset_root: str | None = None) -> TaskRecord:
    task_id = str(
        payload.get("task_id")
        or payload.get("id")
        or payload.get("Question ID")
        or payload.get("question_id")
    )
    question = payload.get("question") or payload.get("Question") or payload.get("prompt")
    if not task_id or not question:
        raise ValueError(f"Task payload is missing required keys: {payload}")

    expected_answer = (
        payload.get("answer")
        or payload.get("expected_answer")
        or payload.get("final_answer")
        or payload.get("Final answer")
    )
    attachment_name = payload.get("file_name")
    attachment_path = payload.get("file_path")
    split = payload.get("split")
    level = payload.get("level") or payload.get("Level")
    ignored_keys = {
        "task_id",
        "id",
        "Question ID",
        "question_id",
        "question",
        "Question",
        "prompt",
        "answer",
        "expected_answer",
        "final_answer",
        "Final answer",
        "file_name",
        "file_path",
        "split",
        "level",
        "Level",
    }
    metadata = {key: value for key, value in payload.items() if key not in ignored_keys}
    return TaskRecord(
        task_id=task_id,
        question=question,
        expected_answer=expected_answer,
        attachment_name=attachment_name,
        attachment_path=attachment_path,
        dataset_root=dataset_root,
        split=split,
        level=int(level) if level is not None and str(level).isdigit() else None,
        metadata=metadata,
    )


def _load_json_file(path: Path) -> list[TaskRecord]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        return [_task_from_mapping(item, dataset_root=str(path.parent)) for item in payload]
    if isinstance(payload, dict) and "tasks" in payload:
        return [
            _task_from_mapping(item, dataset_root=str(path.parent))
            for item in payload["tasks"]
        ]
    raise ValueError(f"Unsupported JSON dataset structure in {path}")


def _load_jsonl_file(path: Path) -> list[TaskRecord]:
    tasks: list[TaskRecord] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tasks.append(_task_from_mapping(json.loads(stripped), dataset_root=str(path.parent)))
    return tasks


def _load_huggingface_dataset(dataset_uri: str) -> list[TaskRecord]:
    parsed = urlparse(dataset_uri)
    repo_id = f"{parsed.netloc}{parsed.path}"
    params = parse_qs(parsed.query)
    split = params.get("split", ["validation"])[0]
    subset = params.get("subset", [None])[0]
    local_root = snapshot_download(repo_id=repo_id, repo_type="dataset")
    dataset = load_dataset(local_root, subset, split=split)
    return [_task_from_mapping(item, dataset_root=local_root) for item in dataset]  # type: ignore[arg-type]


def load_tasks(dataset_path: str | Path) -> list[TaskRecord]:
    if isinstance(dataset_path, Path):
        dataset_path = str(dataset_path)

    if dataset_path.startswith("hf://"):
        return _load_huggingface_dataset(dataset_path)

    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {path}")
    if path.suffix == ".jsonl":
        return _load_jsonl_file(path)
    if path.suffix == ".json":
        return _load_json_file(path)
    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def select_subset(
    tasks: list[TaskRecord],
    subset: str | int | None,
    *,
    full: bool = False,
) -> list[TaskRecord]:
    if full or subset is None:
        return tasks
    if isinstance(subset, str) and subset.isdigit():
        subset = int(subset)
    if isinstance(subset, int):
        return tasks[:subset]
    lowered = subset.lower()
    if lowered in {"sample", "smoke"}:
        return tasks[:3]
    return [
        task
        for task in tasks
        if task.split == subset or task.metadata.get("split") == subset or task.task_id == subset
    ]


__all__ = ["load_tasks", "score_prediction", "select_subset"]
