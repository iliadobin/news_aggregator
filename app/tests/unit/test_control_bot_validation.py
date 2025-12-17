import pytest

from app.bots.control_bot.validation import (
    UserInputError,
    parse_chat_id,
    parse_keywords,
    parse_public_username_or_link,
    parse_threshold,
)


class TestControlBotValidation:
    def test_parse_keywords(self) -> None:
        assert parse_keywords("") == []
        assert parse_keywords("  ") == []
        assert parse_keywords("python, aiogram") == ["python", "aiogram"]
        assert parse_keywords("python\naiogram") == ["python", "aiogram"]
        assert parse_keywords("Python, python, PYTHON") == ["Python"]

    def test_parse_threshold(self) -> None:
        assert parse_threshold("0") == 0.0
        assert parse_threshold("1") == 1.0
        assert parse_threshold("0,7") == 0.7
        with pytest.raises(UserInputError):
            parse_threshold("")
        with pytest.raises(UserInputError):
            parse_threshold("abc")
        with pytest.raises(UserInputError):
            parse_threshold("1.1")

    def test_parse_chat_id(self) -> None:
        assert parse_chat_id("123") == 123
        assert parse_chat_id("-100123") == -100123
        with pytest.raises(UserInputError):
            parse_chat_id("")
        with pytest.raises(UserInputError):
            parse_chat_id("abc")
        with pytest.raises(UserInputError):
            parse_chat_id("@channel")

    def test_parse_public_username_or_link(self) -> None:
        assert parse_public_username_or_link("@Durov") == "@durov"
        assert parse_public_username_or_link("t.me/Durov") == "@durov"
        assert parse_public_username_or_link("https://t.me/Durov?foo=1") == "@durov"
        with pytest.raises(UserInputError):
            parse_public_username_or_link("t.me/+abcdef")

