"""Structured logging configuration."""

import logging
import sys
from typing import Any

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging output."""

    def format(self, record: logging.LogRecord) -> str:
        # Add extra fields if present
        extras = ""
        if hasattr(record, "extra_fields"):
            extra_fields: dict[str, Any] = record.extra_fields  # type: ignore
            extras = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            if extras:
                extras = f" [{extras}]"

        # Format the message
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname
        name = record.name
        message = record.getMessage()

        return f"{timestamp} | {level:8} | {name} | {message}{extras}"


def setup_logging() -> None:
    """Configure application logging."""
    # Get log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Create formatter
    formatter = StructuredFormatter(
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    loggers_config = {
        "uvicorn": log_level,
        "uvicorn.error": log_level,
        "uvicorn.access": log_level,
        "sqlalchemy.engine": logging.WARNING if not settings.DEBUG else logging.INFO,
        "celery": log_level,
        "httpx": logging.WARNING,
    }

    for logger_name, level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds extra context to log messages."""

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        # Add extra fields to the record
        extra = kwargs.get("extra", {})
        if self.extra:
            extra.update(self.extra)
        extra["extra_fields"] = extra.copy()
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(name: str, **context: Any) -> LoggerAdapter:
    """Get a logger with additional context fields.

    Example:
        logger = get_context_logger(__name__, user_id="123", request_id="abc")
        logger.info("Processing request")  # Logs with user_id and request_id
    """
    return LoggerAdapter(get_logger(name), context)
