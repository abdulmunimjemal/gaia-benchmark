from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from gaia_bot.agent.main import GaiaAgent
from gaia_bot.benchmark.dataset import load_tasks, select_subset
from gaia_bot.benchmark.results import (
    completed_task_ids,
    create_run_id,
    ensure_run_directory,
    load_task_results,
    task_workspace,
    write_run_manifest,
    write_summary,
    write_task_result,
)
from gaia_bot.config.settings import SettingsError, load_settings
from gaia_bot.contracts.basemodels import (
    JudgeOutput,
    PlannerDecision,
    SolverOutput,
    TaskRecord,
    TaskRunResult,
)


async def _evaluate(
    subset: str | None,
    full: bool,
    dataset_override: str | None = None,
    resume_run_id: str | None = None,
    parallel: int | None = None,
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
    concurrency = max(1, parallel or settings.max_parallel_tasks)
    write_run_manifest(
        run_dir,
        {
            "dataset": settings.gaia_data_path,
            "subset": subset,
            "full": full,
            "resume_run_id": resume_run_id,
            "parallel": concurrency,
        },
    )
    done = completed_task_ids(run_dir)
    pending = [task for task in selected if task.task_id not in done]
    results = await _run_parallel(
        tasks=pending,
        settings=settings,
        run_id=run_id,
        run_dir=run_dir,
        concurrency=concurrency,
    )

    all_results = load_task_results(run_dir) if (done or results) else []
    summary_path = write_summary(run_dir, all_results)
    print(summary_path)


async def _run_parallel(
    *,
    tasks: list[TaskRecord],
    settings,
    run_id: str,
    run_dir: Path,
    concurrency: int,
) -> list[TaskRunResult]:
    if not tasks:
        return []

    semaphore = asyncio.Semaphore(concurrency)

    async def _worker(task: TaskRecord) -> TaskRunResult:
        async with semaphore:
            agent = GaiaAgent(settings)
            try:
                result = await asyncio.wait_for(
                    agent.solve(
                        task,
                        run_id=run_id,
                        task_workspace=task_workspace(
                            run_dir, task.task_id
                        ),
                    ),
                    timeout=720,  # 12 min per task hard limit
                )
            except BaseException as exc:
                if isinstance(exc, KeyboardInterrupt | SystemExit):
                    raise
                result = _failure_result(
                    task, run_id=run_id, error=exc
                )
            write_task_result(run_dir, result)
            return result

    coroutines = [_worker(task) for task in tasks]
    return [await future for future in asyncio.as_completed(coroutines)]


def _failure_result(task: TaskRecord, *, run_id: str, error: BaseException) -> TaskRunResult:
    planner = PlannerDecision(
        route="web",
        risk="high",
        use_verifier=False,
        answer_shape="short",
        working_plan=["Task failed before completion."],
    )
    solver = SolverOutput(
        answer="",
        confidence="low",
        citations=[],
        reasoning_summary=f"{type(error).__name__}: {error}",
    )
    judge = JudgeOutput(is_sufficient=False, issues=[str(error)], revised_answer="")
    return TaskRunResult(
        run_id=run_id,
        task_id=task.task_id,
        question=task.question,
        answer="",
        raw_answer="",
        scorer_answer="",
        expected_answer=task.expected_answer,
        score=0.0 if task.expected_answer is not None else None,
        passed=False if task.expected_answer is not None else None,
        route="web",
        risk="high",
        retry_count=0,
        error_taxonomy="tool_failure",
        planner=planner,
        solver=solver,
        judge=judge,
        tool_calls=[],
        artifacts_used=[],
        duration_seconds=0.0,
        metadata={**task.metadata, "failure_type": type(error).__name__},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the GAIA benchmark agent.")
    parser.add_argument("--subset", help="Integer count, split name, task id, or 'sample'.")
    parser.add_argument("--full", action="store_true", help="Run the full benchmark.")
    parser.add_argument("--dataset")
    parser.add_argument("--resume-run-id")
    parser.add_argument("--parallel", type=int)
    args = parser.parse_args()
    asyncio.run(
        _evaluate(
            subset=args.subset,
            full=args.full,
            dataset_override=args.dataset,
            resume_run_id=args.resume_run_id,
            parallel=args.parallel,
        )
    )


__all__ = ["main"]
