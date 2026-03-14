from __future__ import annotations

from gaia_bot.models import TaskRecord
from gaia_bot.router import heuristic_route


def test_heuristic_route_detects_direct_task() -> None:
    route = heuristic_route(TaskRecord(task_id="1", question="What is 2 + 2?"))

    assert route.route == "direct"
    assert route.use_verifier is False


def test_heuristic_route_detects_attachment_task() -> None:
    route = heuristic_route(
        TaskRecord(
            task_id="1",
            question="Look at the attached spreadsheet and compute the total.",
            attachment_name="table.csv",
        )
    )

    assert route.route == "artifact"
    assert route.needs_artifact
