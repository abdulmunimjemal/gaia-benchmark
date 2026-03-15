"""Compatibility entrypoint for the live smoke test."""

from gaia_bot.cli.smoke import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
