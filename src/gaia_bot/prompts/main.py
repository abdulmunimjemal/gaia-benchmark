from __future__ import annotations

from gaia_bot.contracts.basemodels import PlannerDecision, SolverOutput, TaskRecord
from gaia_bot.prompts.constants import ROUTE_GUIDANCE


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
    route_guidance = ROUTE_GUIDANCE[planner.route]

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

CRITICAL: You MUST provide a concrete answer. Never say "unable to determine",
"cannot process", or any variation. If tools fail, use your best knowledge.
A wrong answer scores better than no answer on GAIA.

Return the minimal benchmark-ready answer in the answer field.
Use citations for urls, files, or calculations actually used.
"""


def verifier_prompt(
    task: TaskRecord,
    planner: PlannerDecision,
    solver: SolverOutput,
) -> str:
    citations = (
        "\n".join(f"- {item}" for item in solver.citations)
        or "- None"
    )
    return (
        "You are an expert at identifying loopholes or "
        "oversights in reasoning for GAIA benchmark tasks. "
        "Your job is to diagnose the reasoning AND provide "
        "a corrected answer if needed.\n\n"
        "Three response modes:\n"
        "1. Reasoning is sound and answer is correct: "
        "is_sufficient=true, no issues.\n"
        "2. Logic gaps or format problems exist: "
        "is_sufficient=false, list issues, provide "
        "revised_answer with corrected answer.\n"
        "3. Answer is fundamentally wrong: "
        "is_sufficient=false, explain why in issues, "
        "provide revised_answer if you can determine "
        "the correct answer from the citations.\n\n"
        "Check for these specific failure modes:\n"
        "- REASONING ERRORS: Wrong math, wrong logic, "
        "wrong causal chain, miscounting.\n"
        "- TEMPORAL ERRORS: Ignoring time constraints "
        '("as of", "prior to", specific dates).\n'
        "- RETRIEVAL ERRORS: Answer based on wrong "
        "source, wrong entity, or confusing similar "
        "entities.\n"
        "- COMPLETENESS: Missing part of what the "
        "question asks for.\n"
        "- FORMAT: Extra words, units, explanations "
        "that should not be in the answer. The answer "
        "must be bare and minimal for exact-match.\n\n"
        f"Task question:\n{task.question}\n\n"
        f"Route: {planner.route}\n"
        f"Expected answer shape: {planner.answer_shape}\n\n"
        f"Candidate answer:\n{solver.answer}\n\n"
        f"Reasoning summary:\n{solver.reasoning_summary}\n\n"
        f"Citations:\n{citations}\n\n"
        "If the answer needs correction, the "
        "revised_answer must be the minimal, bare "
        "answer only — no explanation, no formatting."
    )


def format_alignment_prompt(
    question: str,
    answer: str,
    answer_shape: str,
) -> str:
    """Dedicated format alignment pass for exact-match."""
    return (
        "You are a GAIA format alignment judge. "
        "Reformat this answer for exact-match scoring. "
        "Do NOT change facts — only fix format.\n\n"
        f"Question:\n{question}\n\n"
        f"Current answer:\n{answer}\n\n"
        f"Detected answer shape: {answer_shape}\n\n"
        "Format rules by shape:\n"
        '- "number": bare number only. No units, no currency '
        "symbols, no commas. Examples: "
        '"42", "3.14", "1000".\n'
        "  - \"how many thousand\" => divide by 1000.\n"
        "  - \"round to\" => apply that rounding.\n"
        "  - \"X decimal places\" => format accordingly.\n"
        '- "list": comma-separated minimal items. '
        'Example: "Paris, London, Tokyo".\n'
        "  - Alphabetize ONLY if asked.\n"
        "  - Preserve source order otherwise.\n"
        '- "short": bare answer. No extra articles '
        "unless part of official name. No trailing "
        "periods. No wrapping quotes.\n"
        '  - Names: "John Smith" not '
        '"John Smith (born 1990)"\n'
        "  - Titles: preserve leading "
        '"The"/"A" if official\n'
        '  - Yes/no: just "Yes" or "No"\n'
        "  - Dates: match question's implied format\n\n"
        "Return ONLY the reformatted answer. "
        "Nothing else. No explanation."
    )


def llm_score_prompt(
    question: str,
    predicted: str,
    expected: str,
) -> str:
    """LLM-based scoring prompt to replace deterministic checks."""
    return (
        "You are a GAIA benchmark scoring judge. "
        "Decide if the predicted answer is equivalent "
        "to the expected answer for scoring purposes.\n\n"
        f"Question:\n{question}\n\n"
        f"Expected answer:\n{expected}\n\n"
        f"Predicted answer:\n{predicted}\n\n"
        "Scoring rules:\n"
        "- Case-insensitive comparison.\n"
        "- Ignore trailing periods, quotes, whitespace.\n"
        '- Numeric equivalence: "3" == "3.0" == "3.00".\n'
        '- Minor format differences are OK: '
        '"New York City" == "New York City".\n'
        "- Leading articles must match if part of an "
        "official title.\n"
        "- Lists: order matters unless question says "
        "otherwise. Items must match semantically.\n"
        "- The predicted answer must convey the same "
        "factual content as the expected answer.\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"match": true} or {"match": false}\n'
        "Nothing else."
    )


__all__ = [
    "direct_prompt",
    "format_alignment_prompt",
    "llm_score_prompt",
    "route_prompt",
    "solver_prompt",
    "verifier_prompt",
]
