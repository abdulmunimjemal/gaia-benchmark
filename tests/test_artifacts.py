from __future__ import annotations

import zipfile
from pathlib import Path

from gaia_bot.artifacts import TaskArtifactManager
from gaia_bot.models import TaskRecord
from gaia_bot.settings import Settings


class _DummyAnthropic:
    pass


def _manager(tmp_path: Path) -> TaskArtifactManager:
    return TaskArtifactManager(
        settings=Settings(),
        task=TaskRecord(task_id="artifact-1", question="Inspect attachment"),
        task_workspace=tmp_path / "workspace",
        anthropic_client=_DummyAnthropic(),  # type: ignore[arg-type]
    )


def test_read_local_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("name,value\nA,1\nB,2\n")

    observation = __import__("asyncio").run(_manager(tmp_path).read_local_path(csv_path))

    assert observation.kind == "table"
    assert "name,value" in Path(observation.stored_path).read_text()


def test_read_local_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    inner = tmp_path / "inner.txt"
    inner.write_text("hello from zip")
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(inner, arcname="inner.txt")

    observation = __import__("asyncio").run(_manager(tmp_path).read_local_path(zip_path))

    assert observation.kind == "archive"
    assert "inner.txt" in Path(observation.stored_path).read_text()
