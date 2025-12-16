"""
Configuration module for the News Aggregator application.

This module uses Pydantic Settings to load and validate configuration from environment variables.
All settings are validated at startup time.
"""

from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvBaseSettings(BaseSettings):
    """
    Base class for settings sections.

    Important: nested settings are instantiated independently (via default_factory),
    so each section must know how to load from `.env` as well.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class DatabaseSettings(EnvBaseSettings):
    """Database connection settings."""

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    user: str = Field(default="news_aggregator", description="PostgreSQL user")
    password: str = Field(default="", description="PostgreSQL password")
    database: str = Field(default="news_aggregator", description="PostgreSQL database name")
    echo: bool = Field(default=False, description="Enable SQLAlchemy echo mode")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")

    @property
    def dsn(self) -> str:
        """Construct PostgreSQL DSN."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class TelegramBotSettings(EnvBaseSettings):
    """Telegram bot settings (classic bot for control)."""

    token: Optional[str] = Field(default=None, description="Telegram bot token")
    admin_ids: list[int] = Field(
        default_factory=list, description="List of admin Telegram user IDs"
    )
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL (if using webhooks)")
    webhook_path: str = Field(default="/webhook", description="Webhook path")

    @field_validator("token")
    @classmethod
    def normalize_token(cls, v: Optional[str]) -> Optional[str]:
        """Normalize token. Token becomes required only when bot is started."""
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> Any:
        """
        Parse admin IDs from common env formats.

        Supported:
        - list[int] (already parsed)
        - JSON list string: "[1,2,3]"
        - comma-separated: "1,2,3"
        - empty string -> []
        """
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return []
            if s.startswith("[") and s.endswith("]"):
                import json

                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            parts = [p.strip() for p in s.split(",") if p.strip() != ""]
            return [int(p) for p in parts]
        return v

    model_config = SettingsConfigDict(
        env_prefix="BOT_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class TelegramUserBotSettings(EnvBaseSettings):
    """Telegram user bot settings (for reading messages from sources)."""

    api_id: Optional[int] = Field(default=None, description="Telegram API ID")
    api_hash: Optional[str] = Field(default=None, description="Telegram API Hash")
    phone: Optional[str] = Field(default=None, description="Phone number for user bot")
    session_name: str = Field(default="news_aggregator_userbot", description="Session name")
    session_dir: Path = Field(
        default=Path("sessions"), description="Directory to store session files"
    )

    @field_validator("api_id", mode="before")
    @classmethod
    def parse_api_id(cls, v: Any) -> Any:
        """Allow missing/blank api_id; require it only when user-bot is started."""
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return None
            if s.isdigit():
                return int(s)
            # placeholder / invalid value -> treat as not configured
            return None
        return v

    @field_validator("api_hash")
    @classmethod
    def normalize_api_hash(cls, v: Optional[str]) -> Optional[str]:
        """Normalize API hash; require it only when user-bot is started."""
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone; require it only when user-bot is started."""
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("session_dir")
    @classmethod
    def create_session_dir(cls, v: Path) -> Path:
        """Ensure session directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    model_config = SettingsConfigDict(
        env_prefix="USERBOT_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class FilterSettings(EnvBaseSettings):
    """Filtering engine settings."""

    enable_keyword: bool = Field(default=True, description="Enable keyword filtering")
    enable_semantic: bool = Field(default=True, description="Enable semantic filtering")
    semantic_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Default semantic similarity threshold"
    )
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        description="Sentence transformer model name",
    )
    embedding_cache_size: int = Field(
        default=1000, description="Number of embeddings to cache in memory"
    )
    max_message_length: int = Field(
        default=4096, description="Maximum message length to process (chars)"
    )

    model_config = SettingsConfigDict(
        env_prefix="FILTER_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class LoggingSettings(EnvBaseSettings):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    json_logs: bool = Field(default=False, description="Enable JSON structured logging")
    log_file: Optional[Path] = Field(default=None, description="Path to log file")
    log_file_max_bytes: int = Field(default=10 * 1024 * 1024, description="Max log file size")
    log_file_backup_count: int = Field(default=5, description="Number of log file backups")

    @field_validator("log_file")
    @classmethod
    def create_log_dir(cls, v: Optional[Path]) -> Optional[Path]:
        """Ensure log directory exists."""
        if v is not None:
            v.parent.mkdir(parents=True, exist_ok=True)
        return v

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppSettings(EnvBaseSettings):
    """Main application settings."""

    environment: Literal["development", "production", "testing"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    timezone: str = Field(default="UTC", description="Default timezone")

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(EnvBaseSettings):
    """Root settings class that aggregates all configuration sections."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    # Telegram settings are intentionally lazy / optional at bootstrap time.
    # They should be instantiated by the bot runners when needed.
    bot: Optional[TelegramBotSettings] = Field(default=None)
    userbot: Optional[TelegramUserBotSettings] = Field(default=None)
    filter: FilterSettings = Field(default_factory=FilterSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # model_config inherited from EnvBaseSettings


# Singleton instance of settings
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create the singleton settings instance.

    Returns:
        Settings: Application settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.

    Useful for testing or when environment variables change at runtime.

    Returns:
        Settings: Newly loaded settings instance
    """
    global _settings
    _settings = Settings()
    return _settings


def get_bot_settings() -> TelegramBotSettings:
    """Load Telegram control-bot settings (token/admins)."""
    return TelegramBotSettings()


def get_userbot_settings() -> TelegramUserBotSettings:
    """Load Telegram user-bot settings (api_id/api_hash/phone/session)."""
    return TelegramUserBotSettings()
