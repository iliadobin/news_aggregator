from __future__ import annotations

from types import SimpleNamespace

from app.bots.control_bot.forward_worker import _build_public_link, _format_delivery_text


class TestForwardWorker:
    def test_build_public_link(self) -> None:
        assert _build_public_link(source_username="durov", telegram_message_id=10) == "https://t.me/durov/10"
        assert _build_public_link(source_username="@durov", telegram_message_id=10) == "https://t.me/durov/10"
        assert _build_public_link(source_username=None, telegram_message_id=10) is None
        assert _build_public_link(source_username="durov", telegram_message_id=0) is None

    def test_format_delivery_text(self) -> None:
        fw = SimpleNamespace(
            filter_id=1,
            message=SimpleNamespace(telegram_message_id=5, text="hello", source_id=1),
            filter=SimpleNamespace(name="MyFilter"),
        )
        text = _format_delivery_text(source_title="Src", source_username="durov", fw=fw)
        assert "Источник: Src" in text
        assert "Фильтр: MyFilter" in text
        assert "https://t.me/durov/5" in text
        assert "hello" in text

