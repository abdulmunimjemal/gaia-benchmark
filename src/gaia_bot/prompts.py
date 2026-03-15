from __future__ import annotations

from gaia_bot.models import PlannerDecision, SolverOutput, TaskRecord

SYSTEM_PROMPT = """You are an autonomous GAIA benchmark agent.

Optimize for exact benchmark correctness, not for prose quality.
Use tools aggressively on risky tasks, but skip them on trivial tasks.
When using sources, prefer authoritative pages and quote only the needed facts.
Prefer primary sources, official pages, and Wikipedia over SEO listicles or recap sites.
Honor every time boundary exactly.
If the task says "as of", "prior to", or specifies a historical version,
do not answer from newer summary pages unless you verify the boundary explicitly.
When using the sandbox, compute and verify exact intermediate results.
For counting, comparison, sorting, and coordinate/distance tasks, gather the facts,
then use code instead of mental math.
Preserve exact title wording,
including leading articles such as "A" or "The",
when the task asks for a complete name.
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
        "web": (
            "Start with targeted search terms, prefer authoritative domains, "
            "and avoid answering from recap or listicle pages when a primary "
            "source or Wikipedia page can answer the task more directly."
        ),
        "code": (
            "Fetch only the exact facts needed, then use the sandbox early for "
            "calculations, parsing, counting, sorting, "
            "and reproducible transforms."
        ),
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

Benchmark constraints:
- Respect exact temporal cutoffs in the question.
- Preserve leading articles in titles and names when they are part of the answer.
- If the answer depends on counting or comparing facts, use the sandbox to verify the final value.

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
