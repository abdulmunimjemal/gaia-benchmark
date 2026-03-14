from __future__ import annotations

import argparse
import asyncio

from gaia_bot.agent import GaiaAgent
from gaia_bot.benchmark import load_tasks, select_subset
from gaia_bot.results import create_run_id, ensure_run_directory, write_summary, write_task_result
from gaia_bot.settings import SettingsError, load_settings


async def _evaluate(subset: str | None, full: bool, dataset_override: str | None = None) -> None:
    settings = load_settings()
    if dataset_override:
        settings.gaia_data_path = dataset_override
    if not settings.gaia_data_path:
        raise SettingsError("GAIA_DATA_PATH must be set in .env or passed with --dataset.")

    tasks = load_tasks(settings.gaia_data_path)
    selected = select_subset(tasks, subset, full=full)
    if not selected:
        raise SettingsError("No tasks selected for evaluation.")

    run_id = create_run_id()
    run_dir = ensure_run_directory(settings.results_dir, run_id)
    agent = GaiaAgent(settings)
    results = []
    for task in selected:
        result = await agent.solve(task, run_id=run_id)
        results.append(result)
        write_task_result(run_dir, result)

    summary_path = write_summary(run_dir, results)
    print(summary_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the GAIA benchmark agent.")
    parser.add_argument("--subset", help="Integer count, split name, task id, or 'sample'.")
    parser.add_argument("--full", action="store_true", help="Run the full benchmark.")
    parser.add_argument("--dataset")
    args = parser.parse_args()
    asyncio.run(_evaluate(subset=args.subset, full=args.full, dataset_override=args.dataset))


if __name__ == "__main__":
    main()
