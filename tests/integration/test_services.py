from __future__ import annotations

import pytest

from gaia_bot.agent import GaiaAgent
from gaia_bot.executor import SandboxExecutor
from gaia_bot.settings import load_settings

pytestmark = pytest.mark.integration


def _has_live_credentials() -> bool:
    try:
        settings = load_settings()
    except Exception:
        return False
    return settings.anthropic_api_key is not None and settings.e2b_api_key is not None


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_live_credentials(),
    reason="Live Anthropic and E2B credentials are required",
)
async def test_live_smoke_services() -> None:
    settings = load_settings()
    agent = GaiaAgent(settings)
    reply = await agent.smoke_anthropic()
    assert "OK" in reply.upper()

    async with SandboxExecutor(settings) as executor:
        result = await executor.execute("print(6 * 7)")
    assert result.ok
    assert "42" in result.stdout or "42" in " ".join(result.results)
