from __future__ import annotations

from types import SimpleNamespace

from gaia_bot.services.executor import _coerce_e2b_execution


def test_coerce_e2b_execution_collects_logs_and_errors() -> None:
    execution = SimpleNamespace(
        logs=SimpleNamespace(stdout=["hello"], stderr=["warn"]),
        results=[SimpleNamespace(text="42", json=None, markdown=None, html=None)],
        error=SimpleNamespace(name="ValueError", value="bad", traceback="trace"),
    )

    result = _coerce_e2b_execution(execution)

    assert result.stdout == "hello"
    assert result.stderr == "warn"
    assert result.results == ["42"]
    assert result.error_name == "ValueError"
    assert not result.ok
