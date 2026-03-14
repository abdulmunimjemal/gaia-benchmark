from __future__ import annotations

import asyncio

from gaia_bot.agent import GaiaAgent
from gaia_bot.executor import SandboxExecutor
from gaia_bot.settings import load_settings


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


if __name__ == "__main__":
    main()
