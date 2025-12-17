"""
Filters management handlers for control-bot (aiogram v3).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bots.control_bot.callbacks import FiltersCb, MenuCb
from app.bots.control_bot.keyboards import filter_actions_kb, filter_mode_select_kb, filters_menu_kb
from app.bots.control_bot.states import CreateFilter, EditFilterKeywords, EditFilterThreshold, EditFilterTopics
from app.bots.control_bot.validation import UserInputError, parse_keywords, parse_threshold
from app.config.settings import TelegramBotSettings
from app.infra.db.models import FilterMode as DbFilterMode
from app.infra.db.repositories import FilterRepository, UserRepository
from app.infra.logging.config import LogContext

logger = logging.getLogger(__name__)

router = Router(name="control_filters")


async def _ensure_user(*, tg_user, user_repo: UserRepository, bot_settings: TelegramBotSettings):
    tg_id = int(tg_user.id)
    with LogContext(user_id=tg_id):
        user, _ = await user_repo.get_or_create_by_telegram_id(
            telegram_id=tg_id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            is_admin=tg_id in set(bot_settings.admin_ids),
        )
        return user


def _filters_list_kb(filters: list[object]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for f in filters:
        fid = int(getattr(f, "id"))
        name = str(getattr(f, "name"))
        is_active = bool(getattr(f, "is_active"))
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅' if is_active else '⏸️'} {name}",
                    callback_data=FiltersCb(action="open", filter_id=fid).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=MenuCb(section="filters").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("filters"))
async def cmd_filters(message: Message) -> None:
    await message.answer("Фильтры:", reply_markup=filters_menu_kb())


@router.callback_query(MenuCb.filter(F.section == "filters"))
async def on_menu_filters(callback: CallbackQuery, callback_data: MenuCb) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("Фильтры:", reply_markup=filters_menu_kb())
    await callback.answer()


@router.callback_query(FiltersCb.filter())
async def on_filters_actions(
    callback: CallbackQuery,
    callback_data: FiltersCb,
    state: FSMContext,
    user_repo: UserRepository,
    filter_repo: FilterRepository,
    bot_settings: TelegramBotSettings,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    user = await _ensure_user(tg_user=callback.from_user, user_repo=user_repo, bot_settings=bot_settings)

    if callback.message is None:
        await callback.answer()
        return

    action = callback_data.action
    fid = callback_data.filter_id
    selected_mode = callback_data.mode

    if action == "create":
        await state.set_state(CreateFilter.name)
        await callback.message.answer("Введите название фильтра одним сообщением:")
        await callback.answer()
        return

    if action == "create_mode":
        data = await state.get_data()
        name = (data.get("name") or "").strip()
        if not name:
            await state.clear()
            await callback.answer("Сессия создания фильтра устарела. Создайте заново.", show_alert=True)
            return
        if selected_mode not in {"keyword_only", "semantic_only", "combined"}:
            await callback.answer("Некорректный режим", show_alert=True)
            return

        created = await filter_repo.create(
            user_id=int(user.id),
            name=name,
            is_active=True,
            mode=DbFilterMode(selected_mode),
            keywords=[],
            topics=[],
        )
        await state.clear()
        await callback.message.edit_text(
            "Фильтр создан:\n\n" + _render_filter(created),
            reply_markup=filter_actions_kb(
                int(created.id),
                is_active=bool(created.is_active),
                mode=_mode_value(getattr(created, "mode", "combined")),
            ),
        )
        await callback.answer()
        return

    if action == "list":
        filters = await filter_repo.get_user_filters(user.id, active_only=False)
        if not filters:
            await callback.message.edit_text(
                "У вас пока нет фильтров. Создайте первый:",
                reply_markup=filters_menu_kb(),
            )
        else:
            await callback.message.edit_text(
                "Ваши фильтры (нажмите, чтобы открыть):",
                reply_markup=_filters_list_kb(filters),
            )
        await callback.answer()
        return

    if fid is None:
        await callback.answer("Не указан фильтр", show_alert=True)
        return

    db_filter = await filter_repo.get(int(fid))
    if db_filter is None or int(db_filter.user_id) != int(user.id):
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    current_mode = _mode_value(getattr(db_filter, "mode", "combined"))

    if action == "open":
        await callback.message.edit_text(
            _render_filter(db_filter),
            reply_markup=filter_actions_kb(
                int(db_filter.id), is_active=bool(db_filter.is_active), mode=current_mode
            ),
        )
        await callback.answer()
        return

    if action == "toggle":
        new_active = not bool(db_filter.is_active)
        await filter_repo.update(int(db_filter.id), is_active=new_active)
        db_filter = await filter_repo.get(int(db_filter.id))
        current_mode = _mode_value(getattr(db_filter, "mode", "combined"))
        await callback.message.edit_text(
            _render_filter(db_filter),
            reply_markup=filter_actions_kb(
                int(db_filter.id), is_active=bool(db_filter.is_active), mode=current_mode
            ),
        )
        await callback.answer("Ок")
        return

    if action == "edit_mode":
        await callback.message.edit_text(
            "Выберите режим фильтра:",
            reply_markup=filter_mode_select_kb(
                filter_id=int(db_filter.id), current_mode=current_mode, for_create=False
            ),
        )
        await callback.answer()
        return

    if action == "set_mode":
        if selected_mode not in {"keyword_only", "semantic_only", "combined"}:
            await callback.answer("Некорректный режим", show_alert=True)
            return
        await filter_repo.update(int(db_filter.id), mode=DbFilterMode(selected_mode))
        db_filter = await filter_repo.get(int(db_filter.id))
        current_mode = _mode_value(getattr(db_filter, "mode", "combined"))
        await callback.message.edit_text(
            _render_filter(db_filter),
            reply_markup=filter_actions_kb(
                int(db_filter.id), is_active=bool(db_filter.is_active), mode=current_mode
            ),
        )
        await callback.answer("Режим обновлён")
        return

    if action == "delete":
        await filter_repo.delete(int(db_filter.id))
        await callback.message.edit_text("Фильтр удалён.", reply_markup=filters_menu_kb())
        await callback.answer()
        return

    if action == "edit_keywords":
        if current_mode == "semantic_only":
            await callback.answer("В режиме 'только семантика' ключевые слова недоступны", show_alert=True)
            return
        await state.set_state(EditFilterKeywords.keywords)
        await state.update_data(filter_id=int(db_filter.id))
        existing = getattr(db_filter, "keywords", None) or []
        current = ", ".join([str(x) for x in existing]) if existing else "—"
        await callback.message.answer(
            "Отправьте ключевые слова (через запятую или с новой строки).\n"
            f"Текущие: {current}"
        )
        await callback.answer()
        return

    if action == "edit_topics":
        if current_mode == "keyword_only":
            await callback.answer("В режиме 'только ключевые слова' темы недоступны", show_alert=True)
            return
        await state.set_state(EditFilterTopics.topics)
        await state.update_data(filter_id=int(db_filter.id))
        existing = getattr(db_filter, "topics", None) or []
        current = ", ".join([str(x) for x in existing]) if existing else "—"
        await callback.message.answer(
            "Отправьте темы для семантики (через запятую или с новой строки).\n"
            "Это 'эталоны смысла', с которыми сравниваются посты.\n"
            f"Текущие: {current}"
        )
        await callback.answer()
        return

    if action == "edit_threshold":
        if current_mode == "keyword_only":
            await callback.answer("В режиме 'только ключевые слова' порог семантики недоступен", show_alert=True)
            return
        await state.set_state(EditFilterThreshold.threshold)
        await state.update_data(filter_id=int(db_filter.id))
        current = float(getattr(db_filter, "semantic_threshold", 0.7))
        await callback.message.answer(
            "Отправьте новый порог семантики (0.0–1.0). "
            f"Текущий: {current}"
        )
        await callback.answer()
        return

    await callback.answer("Неизвестное действие", show_alert=True)


def _render_filter(db_filter) -> str:
    keywords = getattr(db_filter, "keywords", None) or []
    topics = getattr(db_filter, "topics", None) or []
    threshold = float(getattr(db_filter, "semantic_threshold", 0.7))
    mode = _mode_value(getattr(db_filter, "mode", "combined"))
    return (
        f"Фильтр: {db_filter.name}\n"
        f"ID: {db_filter.id}\n"
        f"Статус: {'включён' if db_filter.is_active else 'выключен'}\n"
        f"Режим: {mode}\n"
        f"Ключевые слова ({len(keywords)}): {', '.join(map(str, keywords)) if keywords else '—'}\n"
        f"Темы ({len(topics)}): {', '.join(map(str, topics)) if topics else '—'}\n"
        f"Порог семантики: {threshold}\n"
    )


def _mode_value(mode_obj) -> str:
    if hasattr(mode_obj, "value"):
        return str(getattr(mode_obj, "value"))
    s = str(mode_obj)
    if "." in s:
        s = s.split(".")[-1]
    return s.strip().lower()


@router.message(CreateFilter.name)
async def on_create_filter_name(
    message: Message,
    state: FSMContext,
    user_repo: UserRepository,
    filter_repo: FilterRepository,
    bot_settings: TelegramBotSettings,
) -> None:
    if message.from_user is None:
        return
    user = await _ensure_user(tg_user=message.from_user, user_repo=user_repo, bot_settings=bot_settings)
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Повторите ввод.")
        return
    if len(name) > 255:
        await message.answer("Слишком длинное название (макс 255). Повторите ввод.")
        return
    await state.update_data(name=name)
    await state.set_state(CreateFilter.mode)
    await message.answer(
        "Выберите режим фильтра:",
        reply_markup=filter_mode_select_kb(filter_id=None, current_mode="combined", for_create=True),
    )


@router.message(EditFilterKeywords.keywords)
async def on_edit_filter_keywords(
    message: Message,
    state: FSMContext,
    filter_repo: FilterRepository,
) -> None:
    data = await state.get_data()
    filter_id = data.get("filter_id")
    if filter_id is None:
        await state.clear()
        await message.answer("Сессия редактирования устарела. Откройте фильтр заново.", reply_markup=filters_menu_kb())
        return
    keywords = parse_keywords(message.text or "")
    await filter_repo.update_keywords(int(filter_id), keywords)
    await state.clear()
    updated = await filter_repo.get(int(filter_id))
    current_mode = _mode_value(getattr(updated, "mode", "combined"))
    await message.answer(
        "Ключевые слова обновлены.\n\n" + _render_filter(updated),
        reply_markup=filter_actions_kb(
            int(updated.id), is_active=bool(updated.is_active), mode=current_mode
        ),
    )


@router.message(EditFilterTopics.topics)
async def on_edit_filter_topics(
    message: Message,
    state: FSMContext,
    filter_repo: FilterRepository,
) -> None:
    data = await state.get_data()
    filter_id = data.get("filter_id")
    if filter_id is None:
        await state.clear()
        await message.answer(
            "Сессия редактирования устарела. Откройте фильтр заново.",
            reply_markup=filters_menu_kb(),
        )
        return
    topics = parse_keywords(message.text or "")
    await filter_repo.update_topics(int(filter_id), topics)
    await state.clear()
    updated = await filter_repo.get(int(filter_id))
    current_mode = _mode_value(getattr(updated, "mode", "combined"))
    await message.answer(
        "Темы обновлены.\n\n" + _render_filter(updated),
        reply_markup=filter_actions_kb(int(updated.id), is_active=bool(updated.is_active), mode=current_mode),
    )


@router.message(EditFilterThreshold.threshold)
async def on_edit_filter_threshold(
    message: Message,
    state: FSMContext,
    filter_repo: FilterRepository,
) -> None:
    data = await state.get_data()
    filter_id = data.get("filter_id")
    if filter_id is None:
        await state.clear()
        await message.answer("Сессия редактирования устарела. Откройте фильтр заново.", reply_markup=filters_menu_kb())
        return
    try:
        threshold = parse_threshold(message.text or "")
    except UserInputError as e:
        await message.answer(f"Ошибка: {e}\nПовторите ввод порога (0.0–1.0).")
        return
    await filter_repo.update_threshold(int(filter_id), threshold)
    await state.clear()
    updated = await filter_repo.get(int(filter_id))
    current_mode = _mode_value(getattr(updated, "mode", "combined"))
    await message.answer(
        "Порог обновлён.\n\n" + _render_filter(updated),
        reply_markup=filter_actions_kb(
            int(updated.id), is_active=bool(updated.is_active), mode=current_mode
        ),
    )

