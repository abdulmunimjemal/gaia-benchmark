from __future__ import annotations

import asyncio
import os
from typing import Any

from e2b_code_interpreter import Sandbox

from gaia_bot.config.settings import Settings
from gaia_bot.contracts.basemodels import SandboxExecutionResult


def _coerce_e2b_execution(execution: Any) -> SandboxExecutionResult:
    results: list[str] = []
    for item in getattr(execution, "results", []) or []:
        for field in ("text", "json", "markdown", "html"):
            value = getattr(item, field, None)
            if value:
                results.append(str(value))
                break

    error = getattr(execution, "error", None)
    return SandboxExecutionResult(
        stdout="\n".join(getattr(getattr(execution, "logs", None), "stdout", []) or []),
        stderr="\n".join(getattr(getattr(execution, "logs", None), "stderr", []) or []),
        results=results,
        error_name=getattr(error, "name", None),
        error_value=getattr(error, "value", None),
        traceback=getattr(error, "traceback", None),
    )


class SandboxExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox: Sandbox | None = None

    async def __aenter__(self) -> SandboxExecutor:
        await self.ensure_started()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    async def ensure_started(self) -> Sandbox:
        if self._sandbox is None:
            self.settings.require_service_credentials(require_anthropic=False, require_e2b=True)
            runtime_env = self.settings.runtime_env()
            if "E2B_API_KEY" in runtime_env:
                os.environ["E2B_API_KEY"] = runtime_env["E2B_API_KEY"]
            self._sandbox = await asyncio.to_thread(
                Sandbox.create,
                timeout=self.settings.sandbox_timeout_seconds,
                allow_internet_access=True,
            )
        return self._sandbox

    async def execute(
        self,
        code: str,
        *,
        language: str = "python",
        timeout: int | None = None,
    ) -> SandboxExecutionResult:
        sandbox = await self.ensure_started()
        execution = await asyncio.to_thread(
            sandbox.run_code,
            code=code,
            language=language,
            timeout=timeout or self.settings.sandbox_timeout_seconds,
            request_timeout=self.settings.sandbox_timeout_seconds,
        )
        return _coerce_e2b_execution(execution)

    async def close(self) -> None:
        if self._sandbox is not None:
            sandbox = self._sandbox
            self._sandbox = None
            await asyncio.to_thread(sandbox.kill)


__all__ = ["SandboxExecutor", "_coerce_e2b_execution"]
