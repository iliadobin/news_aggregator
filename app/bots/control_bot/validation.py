"""
Validation and parsing helpers for control-bot user input.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse


class UserInputError(ValueError):
    """Raised when user input cannot be parsed/validated."""


def parse_keywords(text: str) -> list[str]:
    """
    Parse keywords from free-form text.

    Supports comma-separated and newline-separated input.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    # Normalize separators to commas, then split.
    raw = raw.replace("\n", ",")
    parts = [p.strip() for p in raw.split(",")]
    keywords = [p for p in parts if p]
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for kw in keywords:
        if kw.lower() in seen:
            continue
        seen.add(kw.lower())
        out.append(kw)
    return out


def parse_threshold(text: str) -> float:
    """
    Parse semantic threshold in [0.0, 1.0].

    Allows using comma as decimal separator.
    """
    s = (text or "").strip().replace(",", ".")
    if not s:
        raise UserInputError("Порог не задан")
    try:
        value = float(s)
    except ValueError as e:
        raise UserInputError("Порог должен быть числом") from e
    if not (0.0 <= value <= 1.0):
        raise UserInputError("Порог должен быть в диапазоне 0.0–1.0")
    return value


def parse_chat_id(text: str) -> int:
    """
    Parse Telegram chat/channel id.

    Telegram chat ids can be negative (groups/channels).
    """
    s = (text or "").strip()
    if not s:
        raise UserInputError("Chat ID не задан")
    # Accept leading @username? For now we support only numeric ids.
    if s.startswith("@"):
        raise UserInputError("Пока поддерживается только числовой chat_id")
    try:
        chat_id = int(s)
    except ValueError as e:
        raise UserInputError("Chat ID должен быть целым числом") from e
    if chat_id == 0:
        raise UserInputError("Chat ID не может быть 0")
    return chat_id


_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def parse_public_username_or_link(text: str) -> str:
    """
    Parse Telegram public chat reference into '@username'.

    Supports:
    - @username
    - t.me/username
    - https://t.me/username
    - https://telegram.me/username

    Notes:
    - Invite links (t.me/+...) are intentionally rejected here (this flow is for public sources).
    - Returns normalized '@username' (lowercased).
    """
    raw = (text or "").strip()
    if not raw:
        raise UserInputError("Ссылка/тег не задан(а)")

    # Direct @username
    if raw.startswith("@"):
        username = raw[1:].strip()
        if not _USERNAME_RE.match(username):
            raise UserInputError("Некорректный @username")
        return f"@{username.lower()}"

    # Try parsing as URL
    if "://" not in raw:
        raw_url = "https://" + raw
    else:
        raw_url = raw

    try:
        parsed = urlparse(raw_url)
    except Exception as e:
        raise UserInputError("Некорректная ссылка") from e

    host = (parsed.netloc or "").lower()
    if host not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        raise UserInputError("Ожидается ссылка вида t.me/<username> или @username")

    path = (parsed.path or "").strip("/")
    if not path:
        raise UserInputError("В ссылке нет имени канала/чата")

    # Reject invite links like /+abcdef or /joinchat/abcdef
    if path.startswith("+") or path.startswith("joinchat/"):
        raise UserInputError("Пока поддерживаются только публичные каналы/чаты по @username (не invite-ссылки)")

    # Take first path segment as username
    username = path.split("/", 1)[0].strip()
    if not _USERNAME_RE.match(username):
        raise UserInputError("Некорректное имя в ссылке")
    return f"@{username.lower()}"


@dataclass(frozen=True)
class Pagination:
    offset: int
    limit: int

    def next(self, total: int) -> "Pagination":
        if self.offset + self.limit >= total:
            return self
        return Pagination(offset=self.offset + self.limit, limit=self.limit)

    def prev(self) -> "Pagination":
        if self.offset <= 0:
            return self
        return Pagination(offset=max(0, self.offset - self.limit), limit=self.limit)

