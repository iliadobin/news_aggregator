"""
Inline keyboards for control-bot menus.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bots.control_bot.callbacks import FiltersCb, MenuCb, SourcesCb, TargetCb
from app.bots.control_bot.validation import Pagination

_MODE_LABELS: dict[str, str] = {
    "keyword_only": "Только ключевые слова",
    "semantic_only": "Только семантика",
    "combined": "Комбинированный",
}


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Фильтры", callback_data=MenuCb(section="filters").pack())],
            [InlineKeyboardButton(text="Источники", callback_data=MenuCb(section="sources").pack())],
            [InlineKeyboardButton(text="Куда доставлять", callback_data=MenuCb(section="target").pack())],
        ]
    )


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuCb(section="main").pack())]
        ]
    )


def filters_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои фильтры", callback_data=FiltersCb(action="list").pack())],
            [InlineKeyboardButton(text="➕ Создать фильтр", callback_data=FiltersCb(action="create").pack())],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuCb(section="main").pack())],
        ]
    )


def filter_actions_kb(filter_id: int, *, is_active: bool, mode: str) -> InlineKeyboardMarkup:
    toggle_text = "⏸️ Выключить" if is_active else "▶️ Включить"
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=toggle_text, callback_data=FiltersCb(action="toggle", filter_id=filter_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⚙️ Режим: {_MODE_LABELS.get(mode, mode)}",
                callback_data=FiltersCb(action="edit_mode", filter_id=filter_id).pack(),
            )
        ],
    ]

    if mode in ("keyword_only", "combined"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="✍️ Ключевые слова",
                    callback_data=FiltersCb(action="edit_keywords", filter_id=filter_id).pack(),
                )
            ]
        )
    if mode in ("semantic_only", "combined"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🏷️ Темы (семантика)",
                    callback_data=FiltersCb(action="edit_topics", filter_id=filter_id).pack(),
                )
            ]
        )
    if mode in ("semantic_only", "combined"):
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎚️ Порог семантики",
                    callback_data=FiltersCb(action="edit_threshold", filter_id=filter_id).pack(),
                )
            ]
        )

    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить", callback_data=FiltersCb(action="delete", filter_id=filter_id).pack()
                )
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=FiltersCb(action="list").pack())],
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def filter_mode_select_kb(*, filter_id: int | None, current_mode: str | None, for_create: bool) -> InlineKeyboardMarkup:
    """
    Mode selection keyboard.

    - for_create=True: uses action=create_mode (no filter_id required)
    - for_create=False: uses action=set_mode (requires filter_id)
    """
    action = "create_mode" if for_create else "set_mode"
    rows: list[list[InlineKeyboardButton]] = []
    for mode, label in _MODE_LABELS.items():
        prefix = "✅ " if current_mode == mode else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{label}",
                    callback_data=FiltersCb(action=action, filter_id=filter_id, mode=mode).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=FiltersCb(action="open", filter_id=filter_id).pack()
                if not for_create and filter_id is not None
                else MenuCb(section="filters").pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sources_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список источников", callback_data=SourcesCb(action="list").pack())],
            [InlineKeyboardButton(text="➕ Добавить источник", callback_data=SourcesCb(action="add").pack())],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuCb(section="main").pack())],
        ]
    )


def sources_list_kb(
    *,
    items: list[tuple[int, str, bool]],
    pagination: Pagination,
    total: int,
) -> InlineKeyboardMarkup:
    """
    items: list of (source_id, title, is_subscribed)
    """
    rows: list[list[InlineKeyboardButton]] = []
    for source_id, title, is_sub in items:
        action = "unsub" if is_sub else "sub"
        button_text = f"{'✅' if is_sub else '➕'} {title}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=SourcesCb(action=action, source_id=source_id, offset=pagination.offset).pack(),
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if pagination.offset > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=SourcesCb(action="page", offset=pagination.prev().offset).pack(),
            )
        )
    if pagination.offset + pagination.limit < total:
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=SourcesCb(action="page", offset=pagination.next(total).offset).pack(),
            )
        )
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCb(section="sources").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def target_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Показать текущий", callback_data=TargetCb(action="show").pack())],
            [InlineKeyboardButton(text="✅ Установить на этот чат", callback_data=TargetCb(action="set_here").pack())],
            [InlineKeyboardButton(text="✍️ Ввести chat_id", callback_data=TargetCb(action="enter").pack())],
            [InlineKeyboardButton(text="🗑️ Очистить", callback_data=TargetCb(action="clear").pack())],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuCb(section="main").pack())],
        ]
    )

