"""
FSM states for multi-step flows in control-bot.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CreateFilter(StatesGroup):
    name = State()
    mode = State()


class EditFilterKeywords(StatesGroup):
    filter_id = State()
    keywords = State()


class EditFilterTopics(StatesGroup):
    filter_id = State()
    topics = State()


class EditFilterThreshold(StatesGroup):
    filter_id = State()
    threshold = State()


class EnterTargetChatId(StatesGroup):
    chat_id = State()


class AddSource(StatesGroup):
    reference = State()

