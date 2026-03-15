"""Compatibility entrypoint for submission export helpers."""

from gaia_bot.benchmark.submission import export_submission
from gaia_bot.cli.export_submission import main

__all__ = ["export_submission", "main"]


if __name__ == "__main__":
    main()
