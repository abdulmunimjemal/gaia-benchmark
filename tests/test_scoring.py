from __future__ import annotations

from gaia_bot.benchmark.scoring import (
    format_benchmark_answer,
    normalize_exact_match,
    score_prediction,
)


def test_format_benchmark_answer_preserves_leading_article() -> None:
    assert format_benchmark_answer("A Nightmare on Elm Street") == "A Nightmare on Elm Street"


def test_format_benchmark_answer_normalizes_lists_with_spaces() -> None:
    assert format_benchmark_answer("Indonesia,Myanmar", "list") == "Indonesia, Myanmar"


def test_score_prediction_ignores_spacing_around_commas() -> None:
    assert score_prediction("Indonesia,Myanmar", "Indonesia, Myanmar") == 1.0
    assert normalize_exact_match("Santa Clara,   Boston") == "santa clara,boston"


def test_format_benchmark_answer_converts_thousand_units() -> None:
    question = "How many thousand hours would it take?"

    assert format_benchmark_answer("17000", "number", question=question) == "17"
