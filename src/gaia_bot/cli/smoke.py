from __future__ import annotations

import asyncio

from gaia_bot.agent.main import GaiaAgent
from gaia_bot.config.settings import load_settings
from gaia_bot.services.executor import SandboxExecutor


async def _main() -> None:
    settings = load_settings()
    settings.require_service_credentials(require_anthropic=True, require_e2b=True)

    agent = GaiaAgent(settings)
    anthropic_reply = await agent.smoke_anthropic()

    async with SandboxExecutor(settings) as executor:
        sandbox_result = await executor.execute("print('sandbox-ok')")

    print("anthropic:", anthropic_reply)
    print("sandbox stdout:", sandbox_result.stdout.strip())
    print("sandbox ok:", sandbox_result.ok)


def main() -> None:
    asyncio.run(_main())


__all__ = ["main"]
