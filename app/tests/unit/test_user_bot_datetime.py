from __future__ import annotations

from datetime import datetime, timezone

from app.bots.user_bot.handlers import _to_naive_utc


class TestUserBotDatetime:
    def test_to_naive_utc_keeps_naive(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0)
        out = _to_naive_utc(dt)
        assert out.tzinfo is None
        assert out == dt

    def test_to_naive_utc_converts_aware(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        out = _to_naive_utc(dt)
        assert out.tzinfo is None
        assert out == datetime(2025, 1, 1, 12, 0, 0)

