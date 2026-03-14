from __future__ import annotations

import argparse
import json

from gaia_bot.results import compare_run_directories
from gaia_bot.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two GAIA benchmark runs.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()

    settings = load_settings()
    comparison = compare_run_directories(
        settings.results_dir / args.base,
        settings.results_dir / args.candidate,
    )
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
