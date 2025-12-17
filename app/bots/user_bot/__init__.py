"""
User-bot package.

Important:
Do NOT import `runner` at import time. When running modules via `python -m ...`,
import side-effects in `__init__.py` can lead to `runpy` warnings and duplicate initialization.
"""

from __future__ import annotations

from typing import Any

__all__ = ["run_userbot"]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name == "run_userbot":
        from app.bots.user_bot.runner import run_userbot

        return run_userbot
    raise AttributeError(name)

