from __future__ import annotations

import re

from gaia_bot.models import PlannerDecision, TaskRecord
from gaia_bot.scoring import infer_answer_shape

DIRECT_PATTERNS = [
    re.compile(r"^\s*what is\s+\d+\s*[-+*/]\s*\d+\??\s*$", re.IGNORECASE),
    re.compile(r"^\s*what is the capital of ", re.IGNORECASE),
    re.compile(r"^\s*what day comes after ", re.IGNORECASE),
]

CODE_HINTS = (
    "calculate",
    "compute",
    "average",
    "sum",
    "difference",
    "ratio",
    "convert",
    "spreadsheet",
    "csv",
    "tsv",
    "xlsx",
    "excel",
)
WEB_HINTS = (
    "website",
    "official",
    "current",
    "latest",
    "today",
    "article",
    "published",
    "url",
    "wikipedia",
    "news",
)


def heuristic_route(task: TaskRecord) -> PlannerDecision:
    question = task.question.strip()
    lowered = question.lower()
    answer_shape = infer_answer_shape(question)

    if task.attachment_path or task.attachment_name:
        return PlannerDecision(
            route="artifact",
            risk="high",
            use_verifier=True,
            needs_artifact=True,
            needs_code=True,
            working_plan=[
                "Inspect the attached artifact first.",
                "Extract the relevant data from the artifact.",
                "Use sandboxed code for any calculations or parsing.",
            ],
            answer_shape=answer_shape,
        )

    if any(pattern.match(question) for pattern in DIRECT_PATTERNS):
        return PlannerDecision(
            route="direct",
            risk="low",
            use_verifier=False,
            working_plan=["Answer directly with the minimal final answer."],
            answer_shape=answer_shape,
        )

    if any(hint in lowered for hint in CODE_HINTS):
        return PlannerDecision(
            route="code",
            risk="medium",
            use_verifier=True,
            needs_code=True,
            working_plan=[
                "Use sandboxed code to compute or parse the answer.",
                "Cross-check the computed result before finalizing.",
            ],
            answer_shape=answer_shape,
        )

    if any(hint in lowered for hint in WEB_HINTS):
        return PlannerDecision(
            route="web",
            risk="high",
            use_verifier=True,
            needs_web=True,
            research_queries=_seed_queries(question),
            working_plan=[
                "Search broadly for likely authoritative sources.",
                "Fetch the top sources and extract only the needed evidence.",
                "Synthesize the minimal benchmark-ready answer.",
            ],
            answer_shape=answer_shape,
        )

    return PlannerDecision(
        route="web",
        risk="medium",
        use_verifier=True,
        needs_web=True,
        needs_code=bool(re.search(r"\d", question)),
        research_queries=_seed_queries(question),
        working_plan=[
            "Start with targeted search if outside stable world knowledge.",
            "Use code if calculations or transformations are needed.",
            "Return only the minimal benchmark-ready answer.",
        ],
        answer_shape=answer_shape,
    )


def _seed_queries(question: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", question).strip(" ?")
    words = cleaned.split()
    if len(words) <= 8:
        return [cleaned]
    return [cleaned, " ".join(words[:8]), " ".join(words[-8:])]
