"""
Logging configuration module for the News Aggregator application.

Provides unified logging setup with support for:
- Console and file logging
- JSON structured logging
- Rotating file handlers
- Context-aware logging (user_id, message_id, etc.)
"""

import json
import logging
import sys
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from app.config.settings import LoggingSettings, get_settings


# Context variables for correlation IDs
context_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
context_message_id: ContextVar[Optional[int]] = ContextVar("message_id", default=None)
context_filter_id: ContextVar[Optional[int]] = ContextVar("filter_id", default=None)
context_source_id: ContextVar[Optional[int]] = ContextVar("source_id", default=None)


class ContextFilter(logging.Filter):
    """
    Logging filter that adds context variables to log records.

    This allows correlation of logs across different parts of the application
    by tracking user_id, message_id, filter_id, and source_id.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context variables to the log record."""
        record.user_id = context_user_id.get()
        record.message_id = context_message_id.get()
        record.filter_id = context_filter_id.get()
        record.source_id = context_source_id.get()
        return True


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON objects with standard fields plus any context variables.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context variables if present
        if hasattr(record, "user_id") and record.user_id is not None:
            log_data["user_id"] = record.user_id
        if hasattr(record, "message_id") and record.message_id is not None:
            log_data["message_id"] = record.message_id
        if hasattr(record, "filter_id") and record.filter_id is not None:
            log_data["filter_id"] = record.filter_id
        if hasattr(record, "source_id") and record.source_id is not None:
            log_data["source_id"] = record.source_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for better readability in development.

    Uses ANSI color codes to highlight different log levels.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to level name
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )

        # Add context info if present
        context_parts = []
        if hasattr(record, "user_id") and record.user_id is not None:
            context_parts.append(f"user={record.user_id}")
        if hasattr(record, "message_id") and record.message_id is not None:
            context_parts.append(f"msg={record.message_id}")
        if hasattr(record, "filter_id") and record.filter_id is not None:
            context_parts.append(f"filter={record.filter_id}")
        if hasattr(record, "source_id") and record.source_id is not None:
            context_parts.append(f"source={record.source_id}")

        if context_parts:
            context_str = f"[{', '.join(context_parts)}] "
            record.msg = f"{context_str}{record.msg}"

        return super().format(record)


def setup_logging(settings: Optional[LoggingSettings] = None) -> None:
    """
    Configure logging for the application.

    Args:
        settings: Logging settings. If None, will load from global settings.
    """
    if settings is None:
        settings = get_settings().logging

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create context filter
    context_filter = ContextFilter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.level)
    console_handler.addFilter(context_filter)

    if settings.json_logs:
        console_formatter = JSONFormatter()
    else:
        console_formatter = ColoredFormatter(
            fmt=settings.format,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log file is specified)
    if settings.log_file:
        file_handler = RotatingFileHandler(
            filename=settings.log_file,
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(settings.level)
        file_handler.addFilter(context_filter)

        # Always use JSON format for file logs for easier parsing
        file_formatter = JSONFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set levels for third-party loggers to reduce noise
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    root_logger.info(
        "Logging configured",
        extra={
            "extra_data": {
                "level": settings.level,
                "json_logs": settings.json_logs,
                "log_file": str(settings.log_file) if settings.log_file else None,
            }
        },
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for setting correlation IDs in logs.

    Example:
        with LogContext(user_id=123, message_id=456):
            logger.info("Processing message")
            # Logs will include user_id=123 and message_id=456
    """

    def __init__(
        self,
        user_id: Optional[int] = None,
        message_id: Optional[int] = None,
        filter_id: Optional[int] = None,
        source_id: Optional[int] = None,
    ):
        """Initialize log context."""
        self.user_id = user_id
        self.message_id = message_id
        self.filter_id = filter_id
        self.source_id = source_id
        self.tokens: list[Any] = []

    def __enter__(self) -> "LogContext":
        """Set context variables."""
        if self.user_id is not None:
            self.tokens.append(context_user_id.set(self.user_id))
        if self.message_id is not None:
            self.tokens.append(context_message_id.set(self.message_id))
        if self.filter_id is not None:
            self.tokens.append(context_filter_id.set(self.filter_id))
        if self.source_id is not None:
            self.tokens.append(context_source_id.set(self.source_id))
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Reset context variables."""
        for token in self.tokens:
            try:
                token.var.reset(token)
            except ValueError:
                # Token already reset
                pass


# Initialize logging on module import
setup_logging()
