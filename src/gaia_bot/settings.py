from __future__ import annotations

import os
from pathlib import Path

from pydantic import SecretStr
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

    anthropic_api_key: SecretStr | None = None
    e2b_api_key: SecretStr | None = None
    anthropic_model_main: str = "claude-sonnet-4-20250514"
    anthropic_model_judge: str = "claude-sonnet-4-20250514"
    gaia_data_path: str | None = None
    results_dir: Path = Path("artifacts/results")
    max_turns: int = 10
    sandbox_timeout_seconds: int = 90
    http_timeout_seconds: int = 20
    max_search_results: int = 5
    max_fetch_chars: int = 18000
    retry_attempts: int = 1
    claude_cli_path: str = "claude"
    working_directory: Path = Path.cwd()

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
