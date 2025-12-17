"""
Sources management handlers for control-bot (aiogram v3).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram import F
from aiogram import Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bots.control_bot.callbacks import MenuCb, SourcesCb
from app.bots.control_bot.keyboards import sources_list_kb, sources_menu_kb
from app.bots.control_bot.validation import Pagination
from app.bots.control_bot.validation import UserInputError, parse_public_username_or_link
from app.bots.control_bot.states import AddSource
from app.config.settings import TelegramBotSettings
from app.infra.db.models import SourceType as DbSourceType
from app.infra.db.repositories import SourceRepository, SubscriptionRepository, UserRepository
from app.infra.logging.config import LogContext

logger = logging.getLogger(__name__)

router = Router(name="control_sources")


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


@router.message(Command("sources"))
async def cmd_sources(message: Message) -> None:
    await message.answer("Источники:", reply_markup=sources_menu_kb())


@router.message(Command("add_source"))
async def cmd_add_source(message: Message, state: FSMContext) -> None:
    await state.set_state(AddSource.reference)
    await message.answer(
        "Отправьте ссылку на публичный канал/чат или @username.\n"
        "Примеры: `@durov` или `https://t.me/durov`.\n"
        "Пока поддерживаются только публичные источники (без invite-ссылок `t.me/+...`)."
    )


@router.callback_query(MenuCb.filter(F.section == "sources"))
async def on_menu_sources(callback: CallbackQuery, callback_data: MenuCb) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.edit_text("Источники:", reply_markup=sources_menu_kb())
    await callback.answer()


async def _render_sources_page(
    *,
    callback: CallbackQuery,
    user_id: int,
    source_repo: SourceRepository,
    subscription_repo: SubscriptionRepository,
    offset: int,
    limit: int,
) -> None:
    sources = await source_repo.get_active_sources()
    total = len(sources)
    pagination = Pagination(offset=max(0, int(offset)), limit=limit)
    page = sources[pagination.offset : pagination.offset + pagination.limit]

    subs = await subscription_repo.get_user_subscriptions(user_id, active_only=True)
    subscribed_source_ids = {int(s.source_id) for s in subs}

    def _title(src) -> str:
        t = (getattr(src, "title", None) or getattr(src, "username", None) or "").strip()
        if t:
            return t
        return f"chat_id={src.telegram_chat_id}"

    items = [(int(s.id), _title(s), int(s.id) in subscribed_source_ids) for s in page]

    if callback.message is None:
        await callback.answer()
        return

    text = f"Доступные источники: {total}\nНажмите, чтобы подписаться/отписаться."
    await callback.message.edit_text(
        text,
        reply_markup=sources_list_kb(items=items, pagination=pagination, total=total),
    )


@router.callback_query(SourcesCb.filter())
async def on_sources_actions(
    callback: CallbackQuery,
    callback_data: SourcesCb,
    state: FSMContext,
    user_repo: UserRepository,
    source_repo: SourceRepository,
    subscription_repo: SubscriptionRepository,
    bot_settings: TelegramBotSettings,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    user = await _ensure_user(tg_user=callback.from_user, user_repo=user_repo, bot_settings=bot_settings)

    action = callback_data.action
    offset = int(callback_data.offset or 0)

    if action == "add":
        await state.set_state(AddSource.reference)
        if callback.message is not None:
            await callback.message.answer(
                "Отправьте ссылку на публичный канал/чат или @username.\n"
                "Примеры: `@durov` или `https://t.me/durov`.\n"
                "Пока поддерживаются только публичные источники (без invite-ссылок `t.me/+...`)."
            )
        await callback.answer()
        return

    if action in ("list", "page"):
        await _render_sources_page(
            callback=callback,
            user_id=int(user.id),
            source_repo=source_repo,
            subscription_repo=subscription_repo,
            offset=offset,
            limit=10,
        )
        await callback.answer()
        return

    source_id = callback_data.source_id
    if source_id is None:
        await callback.answer("Не указан источник", show_alert=True)
        return

    src = await source_repo.get(int(source_id))
    if src is None:
        await callback.answer("Источник не найден", show_alert=True)
        return

    if action == "sub":
        await subscription_repo.create_subscription(int(user.id), int(source_id))
        await callback.answer("Подписка добавлена")
    elif action == "unsub":
        await subscription_repo.deactivate_subscription(int(user.id), int(source_id))
        await callback.answer("Подписка отключена")
    else:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    await _render_sources_page(
        callback=callback,
        user_id=int(user.id),
        source_repo=source_repo,
        subscription_repo=subscription_repo,
        offset=offset,
        limit=10,
    )


@router.message(AddSource.reference)
async def on_add_source_reference(
    message: Message,
    state: FSMContext,
    bot: Bot,
    source_repo: SourceRepository,
) -> None:
    """
    Add a public source by @username / t.me link.

    We resolve chat via Bot API (getChat) to get numeric chat_id and type,
    then persist Source in DB. User-bot will join and start reading afterwards.
    """
    try:
        ref = parse_public_username_or_link(message.text or "")
    except UserInputError as e:
        await message.answer(f"Ошибка: {e}\nОтправьте корректный @username или ссылку t.me/<username>.")
        return

    try:
        chat = await bot.get_chat(ref)
    except Exception as e:
        logger.exception("Failed to resolve chat via Bot API")
        await message.answer(
            "Не удалось получить информацию об источнике через Bot API.\n"
            "Проверьте, что это публичный канал/чат и что username корректный."
        )
        return

    chat_type = getattr(chat, "type", None)
    if str(chat_type) in {"ChatType.PRIVATE", "private"}:
        await message.answer("Личные чаты как источники через ссылку/username не поддерживаются.")
        return

    if str(chat_type) in {"ChatType.CHANNEL", "channel"}:
        db_type = DbSourceType.CHANNEL
    elif str(chat_type) in {"ChatType.SUPERGROUP", "supergroup", "ChatType.GROUP", "group"}:
        db_type = DbSourceType.GROUP
    else:
        await message.answer(f"Не поддерживаемый тип чата: {chat_type}")
        return

    username = getattr(chat, "username", None) or ref.lstrip("@")
    title = getattr(chat, "title", None) or username
    telegram_chat_id = int(getattr(chat, "id"))

    source, created = await source_repo.get_or_create_by_telegram_chat_id(
        telegram_chat_id=telegram_chat_id,
        title=title,
        username=username,
        type=db_type,
        is_active=True,
    )
    if not created:
        # Ensure it is active and metadata is up to date.
        await source_repo.update(int(source.id), is_active=True, title=title, username=username, type=db_type)

    await state.clear()
    await message.answer(
        f"Источник добавлен: {title} (chat_id={telegram_chat_id}).\n"
        "Юзер-бот скоро попробует вступить и начнёт читать сообщения.\n\n"
        "Откройте /sources → «Список источников», чтобы подписаться на него."
    )

