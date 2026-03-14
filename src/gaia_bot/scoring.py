from __future__ import annotations

import re
from typing import Any

from gaia_bot.models import TaskRunResult

FINAL_ANSWER_RE = re.compile(r"final answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)


def extract_final_answer(text: str | None) -> str:
    if not text:
        return ""
    stripped = str(text).strip().strip("`")
    match = FINAL_ANSWER_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()
    return stripped.strip().strip("`").strip()


def normalize_exact_match(answer: str | None) -> str:
    return extract_final_answer(answer).strip().lower()


def infer_answer_shape(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in ["how many", "what is the number", "what was the total"]):
        return "number"
    if any(token in lowered for token in ["list", "comma-separated", "which of the following"]):
        return "list"
    return "short"


def format_benchmark_answer(answer: str | None, answer_shape: str = "short") -> str:
    cleaned = extract_final_answer(answer)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")

    if answer_shape == "number":
        numeric = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", cleaned)
        if numeric:
            return numeric.group(0).replace(",", "")
        return cleaned.replace(",", "")

    if answer_shape == "list":
        parts = re.split(r"[,;\n]+", cleaned)
        normalized = [format_benchmark_answer(part, "short") for part in parts if part.strip()]
        return ",".join(item for item in normalized if item)

    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip().strip('"').strip("'").strip()
    return cleaned


def score_prediction(predicted: str, expected: str | None) -> float | None:
    if expected is None:
        return None
    return 1.0 if normalize_exact_match(predicted) == normalize_exact_match(expected) else 0.0


def classify_failure(result: TaskRunResult) -> str | None:
    if result.score is None or result.passed:
        return None
    if any(not tool.success for tool in result.tool_calls):
        return "tool_failure"
    if result.route == "artifact" and not result.artifacts_used:
        return "parsing_miss"
    if result.route in {"web", "artifact"} and not result.solver.citations:
        return "retrieval_miss"
    if result.raw_answer and extract_final_answer(result.raw_answer) != (result.answer or ""):
        return "format_miss"
    return "wrong_answer"


def score_breakdown(results: list[TaskRunResult]) -> dict[str, Any]:
    buckets: dict[str, dict[str, int]] = {}
    tool_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}

    for result in results:
        bucket = buckets.setdefault(result.route, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(bool(result.passed))

        if result.error_taxonomy:
            error_counts[result.error_taxonomy] = error_counts.get(result.error_taxonomy, 0) + 1

        for tool in result.tool_calls:
            tool_counts[tool.name] = tool_counts.get(tool.name, 0) + 1

    return {
        "by_route": buckets,
        "tool_counts": tool_counts,
        "error_taxonomy_counts": error_counts,
    }
