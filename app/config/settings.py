"""
Configuration module for the News Aggregator application.

This module uses Pydantic Settings to load and validate configuration from environment variables.
All settings are validated at startup time.
"""

from typing import Literal, Optional
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
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

    model_config = SettingsConfigDict(env_prefix="DB_", case_sensitive=False)


class TelegramBotSettings(BaseSettings):
    """Telegram bot settings (classic bot for control)."""

    token: str = Field(description="Telegram bot token")
    admin_ids: list[int] = Field(
        default_factory=list, description="List of admin Telegram user IDs"
    )
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL (if using webhooks)")
    webhook_path: str = Field(default="/webhook", description="Webhook path")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate that token is not empty."""
        if not v or v.strip() == "":
            raise ValueError("Telegram bot token cannot be empty")
        return v

    model_config = SettingsConfigDict(env_prefix="BOT_", case_sensitive=False)


class TelegramUserBotSettings(BaseSettings):
    """Telegram user bot settings (for reading messages from sources)."""

    api_id: int = Field(description="Telegram API ID")
    api_hash: str = Field(description="Telegram API Hash")
    phone: str = Field(description="Phone number for user bot")
    session_name: str = Field(default="news_aggregator_userbot", description="Session name")
    session_dir: Path = Field(
        default=Path("sessions"), description="Directory to store session files"
    )

    @field_validator("api_hash")
    @classmethod
    def validate_api_hash(cls, v: str) -> str:
        """Validate that API hash is not empty."""
        if not v or v.strip() == "":
            raise ValueError("Telegram API hash cannot be empty")
        return v

    @field_validator("session_dir")
    @classmethod
    def create_session_dir(cls, v: Path) -> Path:
        """Ensure session directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    model_config = SettingsConfigDict(env_prefix="USERBOT_", case_sensitive=False)


class FilterSettings(BaseSettings):
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

    model_config = SettingsConfigDict(env_prefix="FILTER_", case_sensitive=False)


class LoggingSettings(BaseSettings):
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

    model_config = SettingsConfigDict(env_prefix="LOG_", case_sensitive=False)


class AppSettings(BaseSettings):
    """Main application settings."""

    environment: Literal["development", "production", "testing"] = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    timezone: str = Field(default="UTC", description="Default timezone")

    model_config = SettingsConfigDict(env_prefix="APP_", case_sensitive=False)


class Settings(BaseSettings):
    """Root settings class that aggregates all configuration sections."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    bot: TelegramBotSettings = Field(default_factory=TelegramBotSettings)
    userbot: TelegramUserBotSettings = Field(default_factory=TelegramUserBotSettings)
    filter: FilterSettings = Field(default_factory=FilterSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


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
