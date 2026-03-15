from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    """Raised when repository or environment configuration is invalid."""


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for line_number, raw_line in enumerate(dotenv_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise SettingsError(
                f"Malformed {dotenv_path}: line {line_number} must be KEY=value. "
                "If you pasted the raw Anthropic key, rewrite it as "
                "ANTHROPIC_API_KEY=sk-ant-...."
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_optional_quotes(value.strip())
        if not key:
            raise SettingsError(f"Malformed {dotenv_path}: line {line_number} has an empty key.")
        os.environ.setdefault(key, value)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=True,
        extra="ignore",
    )

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    e2b_api_key: SecretStr | None = Field(default=None, alias="E2B_API_KEY")
    anthropic_model_main: str = Field(
        default="claude-sonnet-4-20250514",
        alias="ANTHROPIC_MODEL_MAIN",
    )
    anthropic_model_judge: str = Field(
        default="claude-sonnet-4-20250514",
        alias="ANTHROPIC_MODEL_JUDGE",
    )
    gaia_data_path: str | None = Field(default=None, alias="GAIA_DATA_PATH")
    results_dir: Path = Field(default=Path("artifacts/results"), alias="RESULTS_DIR")
    max_turns: int = Field(default=10, alias="MAX_TURNS")
    sandbox_timeout_seconds: int = Field(default=90, alias="SANDBOX_TIMEOUT_SECONDS")
    http_timeout_seconds: int = Field(default=20, alias="HTTP_TIMEOUT_SECONDS")
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")
    max_fetch_chars: int = Field(default=18000, alias="MAX_FETCH_CHARS")
    max_parallel_tasks: int = Field(default=3, alias="MAX_PARALLEL_TASKS")
    retry_attempts: int = Field(default=2, alias="RETRY_ATTEMPTS")
    claude_cli_path: str = Field(default="claude", alias="CLAUDE_CLI_PATH")
    working_directory: Path = Field(default=Path.cwd(), alias="WORKING_DIRECTORY")

    def require_service_credentials(
        self,
        *,
        require_anthropic: bool = True,
        require_e2b: bool = True,
    ) -> None:
        missing: list[str] = []
        if require_anthropic and self.anthropic_api_key is None:
            missing.append("ANTHROPIC_API_KEY")
        if require_e2b and self.e2b_api_key is None:
            missing.append("E2B_API_KEY")
        if missing:
            joined = ", ".join(missing)
            raise SettingsError(f"Missing required environment variables: {joined}")

    def runtime_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if self.anthropic_api_key is not None:
            env["ANTHROPIC_API_KEY"] = self.anthropic_api_key.get_secret_value()
        if self.e2b_api_key is not None:
            env["E2B_API_KEY"] = self.e2b_api_key.get_secret_value()
        return env


def load_settings(dotenv_path: str | Path = ".env") -> Settings:
    load_dotenv_file(Path(dotenv_path))
    return Settings()


__all__ = ["Settings", "SettingsError", "load_dotenv_file", "load_settings"]
