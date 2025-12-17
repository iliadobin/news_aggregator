"""
Settings / main menu handlers for control-bot (aiogram v3).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram import F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bots.control_bot.callbacks import MenuCb, TargetCb
from app.bots.control_bot.keyboards import main_menu_kb, target_menu_kb
from app.bots.control_bot.states import EnterTargetChatId
from app.bots.control_bot.validation import UserInputError, parse_chat_id
from app.config.settings import TelegramBotSettings
from app.infra.db.repositories import UserRepository
from app.infra.logging.config import LogContext

logger = logging.getLogger(__name__)

router = Router(name="control_settings")


async def _ensure_user(*, message: Message, user_repo: UserRepository, bot_settings: TelegramBotSettings):
    if message.from_user is None:
        return None
    tg_id = int(message.from_user.id)
    with LogContext(user_id=tg_id):
        user, created = await user_repo.get_or_create_by_telegram_id(
            telegram_id=tg_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            is_admin=tg_id in set(bot_settings.admin_ids),
        )
        if created:
            logger.info("Registered new user", extra={"extra_data": {"telegram_id": tg_id}})
        return user


@router.message(CommandStart())
async def cmd_start(message: Message, user_repo: UserRepository, bot_settings: TelegramBotSettings) -> None:
    user = await _ensure_user(message=message, user_repo=user_repo, bot_settings=bot_settings)
    if user is None:
        return
    await message.answer(
        "Привет! Я бот управления агрегатором новостей.\n\n"
        "Выберите раздел:",
        reply_markup=main_menu_kb(),
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message, user_repo: UserRepository, bot_settings: TelegramBotSettings) -> None:
    await _ensure_user(message=message, user_repo=user_repo, bot_settings=bot_settings)
    await message.answer("Настройки и управление:", reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/start — регистрация и меню\n"
        "/settings — меню\n"
        "/filters — фильтры\n"
        "/sources — источники\n"
        "/target — целевой чат\n"
        "/set_target — установить текущий чат как целевой\n"
    )


@router.callback_query(MenuCb.filter(F.section == "main"))
async def on_menu_main(callback: CallbackQuery, callback_data: MenuCb) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
    await callback.answer()

@router.callback_query(MenuCb.filter(F.section == "target"))
async def on_menu_target(callback: CallbackQuery, callback_data: MenuCb) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("Куда доставлять новости:", reply_markup=target_menu_kb())
    await callback.answer()


@router.message(Command("target"))
async def cmd_target(message: Message, user_repo: UserRepository, bot_settings: TelegramBotSettings) -> None:
    await _ensure_user(message=message, user_repo=user_repo, bot_settings=bot_settings)
    await message.answer("Куда доставлять новости:", reply_markup=target_menu_kb())


@router.message(Command("set_target"))
async def cmd_set_target_here(message: Message, user_repo: UserRepository, bot_settings: TelegramBotSettings) -> None:
    user = await _ensure_user(message=message, user_repo=user_repo, bot_settings=bot_settings)
    if user is None:
        return
    # Current chat becomes target for this user.
    await user_repo.update(user.id, target_chat_id=int(message.chat.id))
    await message.answer(f"Готово. Целевой чат установлен: {message.chat.id}")


@router.callback_query(TargetCb.filter())
async def on_target_actions(
    callback: CallbackQuery,
    callback_data: TargetCb,
    state: FSMContext,
    user_repo: UserRepository,
    bot_settings: TelegramBotSettings,
) -> None:
    if callback.message is None or callback.from_user is None:
        await callback.answer()
        return
    tg_id = int(callback.from_user.id)
    with LogContext(user_id=tg_id):
        user, _ = await user_repo.get_or_create_by_telegram_id(
            telegram_id=tg_id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name,
            is_admin=tg_id in set(bot_settings.admin_ids),
        )

        if callback_data.action == "show":
            current = user.target_chat_id
            await callback.message.answer(
                f"Текущий целевой чат: {current}" if current is not None else "Целевой чат ещё не задан.",
                reply_markup=target_menu_kb(),
            )
        elif callback_data.action == "set_here":
            chat_id = int(callback.message.chat.id)
            await user_repo.update(user.id, target_chat_id=chat_id)
            await callback.message.answer(f"Целевой чат установлен: {chat_id}", reply_markup=target_menu_kb())
        elif callback_data.action == "clear":
            await user_repo.update(user.id, target_chat_id=None)
            await callback.message.answer("Целевой чат очищен.", reply_markup=target_menu_kb())
        elif callback_data.action == "enter":
            await state.set_state(EnterTargetChatId.chat_id)
            await callback.message.answer("Введите числовой chat_id сообщением (например -100123...).")
        else:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
    await callback.answer()


@router.message(EnterTargetChatId.chat_id)
async def on_enter_target_chat_id(
    message: Message,
    state,
    user_repo: UserRepository,
    bot_settings: TelegramBotSettings,
) -> None:
    # `state` is FSMContext; keep it untyped to avoid mypy plugin setup issues here.
    user = await _ensure_user(message=message, user_repo=user_repo, bot_settings=bot_settings)
    if user is None:
        return
    try:
        chat_id = parse_chat_id(message.text or "")
    except UserInputError as e:
        await message.answer(f"Ошибка: {e}\nПовторите ввод chat_id.")
        return
    await user_repo.update(user.id, target_chat_id=chat_id)
    await state.clear()
    await message.answer(f"Целевой чат установлен: {chat_id}", reply_markup=target_menu_kb())

