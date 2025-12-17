from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bots.control_bot.callbacks import FiltersCb, SourcesCb, TargetCb
from app.bots.control_bot.handlers_filters import on_create_filter_name, on_filters_actions
from app.bots.control_bot.handlers_settings import cmd_start, on_target_actions
from app.bots.control_bot.handlers_sources import cmd_add_source, on_add_source_reference, on_sources_actions
from app.bots.control_bot.states import AddSource, CreateFilter, EnterTargetChatId
from app.config.settings import TelegramBotSettings


def _tg_user(user_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, username="u", first_name="f", last_name="l")


def _message(*, text: str = "", user_id: int = 1, chat_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        from_user=_tg_user(user_id),
        chat=SimpleNamespace(id=chat_id),
        answer=AsyncMock(),
    )


def _callback(*, user_id: int = 1, chat_id: int = 10) -> SimpleNamespace:
    msg = SimpleNamespace(chat=SimpleNamespace(id=chat_id), answer=AsyncMock(), edit_text=AsyncMock())
    return SimpleNamespace(from_user=_tg_user(user_id), message=msg, answer=AsyncMock())


class TestControlBotHandlers:
    async def test_start_registers_user_and_shows_menu(self) -> None:
        message = _message(text="/start", user_id=42, chat_id=42)
        user_repo = SimpleNamespace(get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=1), True)))
        settings = TelegramBotSettings(token="x", admin_ids=[42])

        await cmd_start(message=message, user_repo=user_repo, bot_settings=settings)

        user_repo.get_or_create_by_telegram_id.assert_awaited_once()
        message.answer.assert_awaited_once()

    async def test_filters_create_sets_state(self) -> None:
        callback = _callback(user_id=1)
        state = SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())
        user_repo = SimpleNamespace(get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=1), False)))
        filter_repo = SimpleNamespace()
        settings = TelegramBotSettings(token="x", admin_ids=[])

        await on_filters_actions(
            callback=callback,
            callback_data=FiltersCb(action="create"),
            state=state,
            user_repo=user_repo,
            filter_repo=filter_repo,
            bot_settings=settings,
        )

        state.set_state.assert_awaited_once_with(CreateFilter.name)
        callback.message.answer.assert_awaited()

    async def test_create_filter_name_asks_for_mode(self) -> None:
        message = _message(text="My filter", user_id=1)
        state = SimpleNamespace(clear=AsyncMock(), set_state=AsyncMock(), update_data=AsyncMock())
        user_repo = SimpleNamespace(get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=7), False)))
        filter_repo = SimpleNamespace(create=AsyncMock())
        settings = TelegramBotSettings(token="x", admin_ids=[])

        await on_create_filter_name(
            message=message,
            state=state,
            user_repo=user_repo,
            filter_repo=filter_repo,
            bot_settings=settings,
        )

        filter_repo.create.assert_not_called()
        state.update_data.assert_awaited()
        state.set_state.assert_awaited_once_with(CreateFilter.mode)
        message.answer.assert_awaited()

    async def test_create_filter_mode_creates_filter(self) -> None:
        callback = _callback(user_id=1)
        state = SimpleNamespace(get_data=AsyncMock(return_value={"name": "My filter"}), clear=AsyncMock())
        user_repo = SimpleNamespace(get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=1), False)))
        created = SimpleNamespace(id=10, user_id=1, name="My filter", is_active=True, keywords=[], semantic_threshold=0.7, mode="keyword_only")
        filter_repo = SimpleNamespace(create=AsyncMock(return_value=created), get_user_filters=AsyncMock())
        settings = TelegramBotSettings(token="x", admin_ids=[])

        await on_filters_actions(
            callback=callback,
            callback_data=FiltersCb(action="create_mode", mode="keyword_only"),
            state=state,
            user_repo=user_repo,
            filter_repo=filter_repo,
            bot_settings=settings,
        )

        filter_repo.create.assert_awaited_once()
        state.clear.assert_awaited_once()
        callback.message.edit_text.assert_awaited()

    async def test_sources_subscribe_calls_repo(self) -> None:
        callback = _callback(user_id=1)
        state = SimpleNamespace(set_state=AsyncMock())
        user_repo = SimpleNamespace(get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=1), False)))
        src_obj = SimpleNamespace(id=2, telegram_chat_id=-100, title="Channel", username=None, is_active=True)
        source_repo = SimpleNamespace(get=AsyncMock(return_value=src_obj), get_active_sources=AsyncMock(return_value=[src_obj]))
        subscription_repo = SimpleNamespace(
            create_subscription=AsyncMock(),
            deactivate_subscription=AsyncMock(),
            get_user_subscriptions=AsyncMock(return_value=[SimpleNamespace(source_id=2)]),
        )
        settings = TelegramBotSettings(token="x", admin_ids=[])

        await on_sources_actions(
            callback=callback,
            callback_data=SourcesCb(action="sub", source_id=2, offset=0),
            state=state,
            user_repo=user_repo,
            source_repo=source_repo,
            subscription_repo=subscription_repo,
            bot_settings=settings,
        )

        subscription_repo.create_subscription.assert_awaited_once_with(1, 2)
        callback.message.edit_text.assert_awaited()

    async def test_add_source_command_sets_state(self) -> None:
        message = _message(text="/add_source", user_id=1)
        state = SimpleNamespace(set_state=AsyncMock())
        await cmd_add_source(message=message, state=state)
        state.set_state.assert_awaited_once_with(AddSource.reference)

    async def test_add_source_reference_resolves_and_creates_source(self) -> None:
        message = _message(text="https://t.me/durov", user_id=1)
        state = SimpleNamespace(clear=AsyncMock())
        bot = SimpleNamespace(
            get_chat=AsyncMock(
                return_value=SimpleNamespace(id=-100123, type="channel", username="durov", title="Durov")
            )
        )
        source_repo = SimpleNamespace(
            get_or_create_by_telegram_chat_id=AsyncMock(return_value=(SimpleNamespace(id=1), True)),
            update=AsyncMock(),
        )
        await on_add_source_reference(
            message=message,
            state=state,
            bot=bot,
            source_repo=source_repo,
        )
        bot.get_chat.assert_awaited()
        source_repo.get_or_create_by_telegram_chat_id.assert_awaited()
        state.clear.assert_awaited_once()
        message.answer.assert_awaited()

    async def test_target_enter_sets_fsm_state(self) -> None:
        callback = _callback(user_id=1, chat_id=99)
        state = SimpleNamespace(set_state=AsyncMock())
        user_repo = SimpleNamespace(
            get_or_create_by_telegram_id=AsyncMock(return_value=(SimpleNamespace(id=1, target_chat_id=None), False)),
            update=AsyncMock(),
        )
        settings = TelegramBotSettings(token="x", admin_ids=[])

        await on_target_actions(
            callback=callback,
            callback_data=TargetCb(action="enter"),
            state=state,
            user_repo=user_repo,
            bot_settings=settings,
        )

        state.set_state.assert_awaited_once_with(EnterTargetChatId.chat_id)

