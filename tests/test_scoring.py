from __future__ import annotations

from gaia_bot.scoring import extract_final_answer, format_benchmark_answer, score_prediction


def test_extract_final_answer_removes_prefix() -> None:
    assert extract_final_answer("FINAL ANSWER: Paris") == "Paris"


def test_format_benchmark_answer_normalizes_numbers() -> None:
    assert format_benchmark_answer("FINAL ANSWER: 1,234 people", "number") == "1234"


def test_score_prediction_uses_exact_match_normalization() -> None:
    assert score_prediction("FINAL ANSWER: Paris", "paris") == 1.0
