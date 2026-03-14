from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_dataset_path() -> Path:
    return Path(__file__).parent / "fixtures" / "gaia_sample.jsonl"
