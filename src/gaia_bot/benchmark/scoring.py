from __future__ import annotations

import re
from typing import Any

from gaia_bot.contracts.basemodels import TaskRunResult

FINAL_ANSWER_RE = re.compile(r"final answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)
SEPARATOR_RE = re.compile(r"\s*,\s*")


def extract_final_answer(text: str | None) -> str:
    if not text:
        return ""
    stripped = str(text).strip().strip("`")
    match = FINAL_ANSWER_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()
    return stripped.strip().strip("`").strip()


def normalize_exact_match(answer: str | None) -> str:
    normalized = extract_final_answer(answer)
    # Normalize unicode quotes and dashes
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = normalized.replace("\u2013", "-").replace("\u2014", "-")
    # Collapse whitespace and strip trailing punctuation
    normalized = re.sub(r"\s+", " ", normalized).strip().strip(".")
    normalized = SEPARATOR_RE.sub(",", normalized)
    # Strip wrapping quotes if present
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized.lower()


def infer_answer_shape(question: str) -> str:
    lowered = question.lower()
    number_tokens = [
        "how many",
        "what is the number",
        "what was the total",
        "what is the total",
        "how much",
        "what percentage",
        "what is the difference",
        "how far",
        "how long",
        "how old",
        "what year",
        "in what year",
        "what was the population",
        "round to",
        "decimal places",
    ]
    if any(token in lowered for token in number_tokens):
        return "number"
    list_tokens = [
        "list",
        "comma-separated",
        "which of the following",
        "name all",
        "list all",
        "what are the",
        "name the",
    ]
    if any(token in lowered for token in list_tokens):
        return "list"
    return "short"


def format_benchmark_answer(
    answer: str | None,
    answer_shape: str = "short",
    question: str | None = None,
) -> str:
    cleaned = extract_final_answer(answer)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")

    if answer_shape == "number":
        numeric = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", cleaned)
        if numeric:
            value = numeric.group(0).replace(",", "")
            if question and _expects_thousands_value(question):
                try:
                    thousands = float(value) / 1000
                except ValueError:
                    return value
                return _stringify_number(thousands)
            return value
        return cleaned.replace(",", "")

    if answer_shape == "list":
        parts = re.split(r"[,;\n]+", cleaned)
        normalized = [
            format_benchmark_answer(part, "short", question=question)
            for part in parts
            if part.strip()
        ]
        return ", ".join(item for item in normalized if item)

    cleaned = cleaned.strip().strip('"').strip("'").strip()
    return cleaned


def _expects_thousands_value(question: str) -> bool:
    lowered = question.lower()
    return "how many thousand" in lowered or "in thousands" in lowered


def _stringify_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    rendered = f"{value:.6f}".rstrip("0").rstrip(".")
    return rendered


def score_prediction(predicted: str, expected: str | None) -> float | None:
    if expected is None:
        return None
    return 1.0 if normalize_exact_match(predicted) == normalize_exact_match(expected) else 0.0


def classify_failure(result: TaskRunResult) -> str | None:
    if result.score is None or result.passed:
        return None

    # "Unable to determine" style answers are retrieval failures, not format misses
    answer_lower = (result.answer or "").lower()
    is_punt = any(
        phrase in answer_lower
        for phrase in ("unable to determine", "cannot process", "unable to")
    )

    if any(not tool.success for tool in result.tool_calls):
        return "tool_failure"
    if result.route == "artifact" and not result.artifacts_used:
        return "parsing_miss"
    if is_punt:
        return "retrieval_miss"
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


__all__ = [
    "classify_failure",
    "extract_final_answer",
    "format_benchmark_answer",
    "infer_answer_shape",
    "normalize_exact_match",
    "score_breakdown",
    "score_prediction",
]
