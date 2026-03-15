from __future__ import annotations

import argparse

from gaia_bot.benchmark.submission import export_submission


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a GAIA leaderboard JSONL submission.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    print(export_submission(run_id=args.run_id, output=args.output))


__all__ = ["main"]
