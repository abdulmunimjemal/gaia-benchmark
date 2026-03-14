from __future__ import annotations

from pathlib import Path

import pytest

from gaia_bot.settings import SettingsError, load_dotenv_file


def test_load_dotenv_file_rejects_raw_secret(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("sk-ant-secret-value\n")

    with pytest.raises(SettingsError, match="must be KEY=value"):
        load_dotenv_file(dotenv)
