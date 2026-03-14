from __future__ import annotations

from gaia_bot.models import PlannerDecision, TaskRecord

SYSTEM_PROMPT = """You are an autonomous GAIA benchmark agent.

Work carefully, prefer exact evidence, and only use tools when they improve confidence.
Use the sandbox tool for calculations, parsing, and reproducible transformations.
Use the search and fetch tools for internet research.
When you cite evidence, name the exact URL or calculation source used.
"""


def planner_prompt(task: TaskRecord) -> str:
    return f"""Analyze the GAIA task below and return a compact execution plan.

Task ID: {task.task_id}
Question:
{task.question}

Decide whether web research is needed, whether sandboxed code execution is
needed, suggest up to 5 search queries, and outline a short working plan.
"""


def solver_prompt(
    task: TaskRecord,
    planner: PlannerDecision,
    critique: list[str] | None = None,
) -> str:
    critique_text = ""
    if critique:
        critique_text = (
            "Address these judge concerns before finalizing:\n- "
            + "\n- ".join(critique)
        )

    plan_lines = "\n".join(f"- {step}" for step in planner.working_plan) or "- Solve directly"
    query_lines = "\n".join(f"- {query}" for query in planner.research_queries) or "- None"
    return f"""Solve the GAIA benchmark task below.

Task ID: {task.task_id}
Question:
{task.question}

Planner analysis:
- needs_web: {planner.needs_web}
- needs_code: {planner.needs_code}
- answer_shape: {planner.answer_shape}
Working plan:
{plan_lines}
Suggested research queries:
{query_lines}

{critique_text}

Use the available tools when they improve correctness. Keep the final answer concise and exact.
"""


def judge_prompt(task: TaskRecord, solver_answer: str, citations: list[str]) -> str:
    evidence = "\n".join(f"- {item}" for item in citations) or "- No explicit citations recorded"
    return f"""Review the candidate answer for this GAIA task.

Task:
{task.question}

Candidate answer:
{solver_answer}

Evidence summary:
{evidence}

Decide whether the answer is sufficient. If not, explain the issues and provide
a revised answer when possible.
"""
