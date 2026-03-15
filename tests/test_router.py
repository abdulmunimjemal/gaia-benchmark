from __future__ import annotations

from gaia_bot.models import TaskRecord
from gaia_bot.routing import heuristic_route


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


def test_heuristic_route_detects_web_plus_code_task() -> None:
    route = heuristic_route(
        TaskRecord(
            task_id="1",
            question=(
                "If Eliud Kipchoge could maintain his record-making marathon pace indefinitely, "
                "how many thousand hours would it take him to run the distance between the Earth "
                "and the Moon its closest approach? Please use the minimum perigee value on the "
                "Wikipedia page for the Moon when carrying out your calculation."
            ),
        )
    )

    assert route.route == "code"
    assert route.needs_web
    assert route.needs_code


def test_heuristic_route_detects_historical_counting_task() -> None:
    route = heuristic_route(
        TaskRecord(
            task_id="1",
            question=(
                "I'd like to learn more about some popular reality television competition shows. "
                "As of the end of the 44th season of the American version of Survivor, how many "
                "more unique winners have there been compared to the number of winners of "
                "American Idol?"
            ),
        )
    )

    assert route.route == "code"
    assert route.needs_web
    assert route.needs_code
