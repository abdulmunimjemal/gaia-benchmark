from __future__ import annotations

import argparse
import asyncio

from gaia_bot.agent import GaiaAgent
from gaia_bot.benchmark import load_tasks
from gaia_bot.results import (
    create_run_id,
    ensure_run_directory,
    task_workspace,
    write_run_manifest,
    write_task_result,
)
from gaia_bot.settings import SettingsError, load_settings


async def _run_task(task_id: str, dataset_override: str | None = None) -> None:
    settings = load_settings()
    if dataset_override:
        settings.gaia_data_path = dataset_override
    if not settings.gaia_data_path:
        raise SettingsError("GAIA_DATA_PATH must be set in .env or passed with --dataset.")

    tasks = load_tasks(settings.gaia_data_path)
    task = next((item for item in tasks if item.task_id == task_id), None)
    if task is None:
        raise SettingsError(f"Task {task_id} not found in dataset {settings.gaia_data_path}.")

    agent = GaiaAgent(settings)
    run_id = create_run_id()
    run_dir = ensure_run_directory(settings.results_dir, run_id)
    write_run_manifest(
        run_dir,
        {"dataset": settings.gaia_data_path, "mode": "single", "task_id": task_id},
    )
    result = await agent.solve(
        task,
        run_id=run_id,
        task_workspace=task_workspace(run_dir, task.task_id),
    )
    destination = write_task_result(run_dir, result)
    print(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single GAIA task.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--dataset")
    args = parser.parse_args()
    asyncio.run(_run_task(task_id=args.task_id, dataset_override=args.dataset))


if __name__ == "__main__":
    main()
