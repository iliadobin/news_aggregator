"""
CallbackData definitions for control-bot inline keyboards (aiogram v3).
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    section: str  # main|filters|sources|target


class FiltersCb(CallbackData, prefix="flt"):
    action: str  # list|create|open|toggle|delete|edit_keywords|edit_topics|edit_threshold|edit_mode|set_mode|create_mode
    filter_id: int | None = None
    mode: str | None = None


class SourcesCb(CallbackData, prefix="src"):
    action: str  # list|sub|unsub|page|add
    source_id: int | None = None
    offset: int = 0


class TargetCb(CallbackData, prefix="tgt"):
    action: str  # show|set_here|enter|clear

