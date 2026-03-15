"""Compatibility entrypoint for run comparison helpers."""

from gaia_bot.benchmark.compare import compare_run_directories
from gaia_bot.cli.compare_runs import main

__all__ = ["compare_run_directories", "main"]


if __name__ == "__main__":
    main()
