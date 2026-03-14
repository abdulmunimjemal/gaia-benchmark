from __future__ import annotations

from gaia_bot.models import PlannerDecision, SolverOutput, TaskRecord

SYSTEM_PROMPT = """You are an autonomous GAIA benchmark agent.

Optimize for exact benchmark correctness, not for prose quality.
Use tools aggressively on risky tasks, but skip them on trivial tasks.
When using sources, prefer authoritative pages and quote only the needed facts.
When using the sandbox, compute and verify exact intermediate results.
The final answer must be minimal and score-friendly: no explanation, no markdown, no extra words.
"""


def route_prompt(task: TaskRecord, heuristic: PlannerDecision) -> str:
    attachment_note = ""
    if task.attachment_name or task.attachment_path:
        attachment_note = (
            f"\nAttachment detected: {task.attachment_name or task.attachment_path}\n"
            "Route this as artifact-heavy unless there is a clear reason not to."
        )
    return f"""Classify this GAIA task into one of: direct, web, code, artifact.

Task ID: {task.task_id}
Question:
{task.question}
{attachment_note}

Heuristic baseline:
- route: {heuristic.route}
- risk: {heuristic.risk}
- answer_shape: {heuristic.answer_shape}

Decide the best route, whether verifier is needed, whether web/code/artifact tools are needed,
up to 5 search queries, and a short working plan.
"""


def direct_prompt(task: TaskRecord, planner: PlannerDecision) -> str:
    return f"""Answer this low-risk GAIA task directly.

Task ID: {task.task_id}
Question:
{task.question}

Return the exact final answer only in the answer field. No explanation in the answer field.
Confidence should reflect whether the answer is trivial or certain.
"""


def solver_prompt(
    task: TaskRecord,
    planner: PlannerDecision,
    *,
    attachment_summary: str = "",
    critique: list[str] | None = None,
) -> str:
    critique_text = ""
    if critique:
        critique_text = "Fix these issues from the verifier:\n- " + "\n- ".join(critique)

    plan_lines = "\n".join(f"- {step}" for step in planner.working_plan) or "- Solve directly"
    query_lines = "\n".join(f"- {query}" for query in planner.research_queries) or "- None"

    route_guidance = {
        "web": "Use broad search first, then fetch the best sources and cite the exact urls used.",
        "code": "Use the sandbox early for calculations, parsing, and reproducible transforms.",
        "artifact": (
            "Inspect the task attachment first. "
            "Extract the artifact contents before searching the web."
        ),
        "direct": "No tools should be needed unless confidence drops.",
    }[planner.route]

    return f"""Solve this GAIA benchmark task.

Task ID: {task.task_id}
Question:
{task.question}

Route:
- route: {planner.route}
- risk: {planner.risk}
- answer_shape: {planner.answer_shape}
- needs_web: {planner.needs_web}
- needs_code: {planner.needs_code}
- needs_artifact: {planner.needs_artifact}

Working plan:
{plan_lines}

Seed queries:
{query_lines}

Attachment summary:
{attachment_summary or "None"}

Route guidance:
{route_guidance}

{critique_text}

Return the minimal benchmark-ready answer in the answer field.
Use citations for urls, files, or calculations actually used.
"""


def verifier_prompt(
    task: TaskRecord,
    planner: PlannerDecision,
    solver: SolverOutput,
) -> str:
    citations = "\n".join(f"- {item}" for item in solver.citations) or "- None"
    return f"""Review this candidate GAIA answer for benchmark scoring risk.

Task:
{task.question}

Route:
- {planner.route}
- answer_shape: {planner.answer_shape}

Candidate answer:
{solver.answer}

Reasoning summary:
{solver.reasoning_summary}

Citations:
{citations}

Decide if the answer is sufficient, grounded, and minimally formatted for exact-match scoring.
If not, list the issues and provide a revised answer that is score-ready.
"""
