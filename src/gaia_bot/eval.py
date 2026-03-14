from __future__ import annotations

import argparse
import asyncio

from gaia_bot.agent import GaiaAgent
from gaia_bot.benchmark import load_tasks, select_subset
from gaia_bot.results import (
    completed_task_ids,
    create_run_id,
    ensure_run_directory,
    task_workspace,
    write_run_manifest,
    write_summary,
    write_task_result,
)
from gaia_bot.settings import SettingsError, load_settings


async def _evaluate(
    subset: str | None,
    full: bool,
    dataset_override: str | None = None,
    resume_run_id: str | None = None,
) -> None:
    settings = load_settings()
    if dataset_override:
        settings.gaia_data_path = dataset_override
    if not settings.gaia_data_path:
        raise SettingsError("GAIA_DATA_PATH must be set in .env or passed with --dataset.")

    tasks = load_tasks(settings.gaia_data_path)
    selected = select_subset(tasks, subset, full=full)
    if not selected:
        raise SettingsError("No tasks selected for evaluation.")

    run_id = resume_run_id or create_run_id()
    run_dir = ensure_run_directory(settings.results_dir, run_id)
    write_run_manifest(
        run_dir,
        {
            "dataset": settings.gaia_data_path,
            "subset": subset,
            "full": full,
            "resume_run_id": resume_run_id,
        },
    )
    done = completed_task_ids(run_dir)
    agent = GaiaAgent(settings)
    results = []
    for task in selected:
        if task.task_id in done:
            continue
        result = await agent.solve(
            task,
            run_id=run_id,
            task_workspace=task_workspace(run_dir, task.task_id),
        )
        results.append(result)
        write_task_result(run_dir, result)

    all_results = results
    if done:
        from gaia_bot.results import load_task_results

        all_results = load_task_results(run_dir)
    summary_path = write_summary(run_dir, all_results)
    print(summary_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the GAIA benchmark agent.")
    parser.add_argument("--subset", help="Integer count, split name, task id, or 'sample'.")
    parser.add_argument("--full", action="store_true", help="Run the full benchmark.")
    parser.add_argument("--dataset")
    parser.add_argument("--resume-run-id")
    args = parser.parse_args()
    asyncio.run(
        _evaluate(
            subset=args.subset,
            full=args.full,
            dataset_override=args.dataset,
            resume_run_id=args.resume_run_id,
        )
    )


if __name__ == "__main__":
    main()
