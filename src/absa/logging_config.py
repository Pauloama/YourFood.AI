"""Structured logging configuration for the ABSA pipeline.

Uses structlog when available, falls back to standard logging.
Respects privacy: does not log full review text by default.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

# Patterns for PII masking
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,3}\)?[\s.-]?\d{4,5}[\s.-]?\d{4}"
)


def mask_pii(text: str) -> str:
    """Mask email addresses and phone numbers in text."""
    text = _EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
    text = _PHONE_PATTERN.sub("[PHONE_REDACTED]", text)
    return text


def _redact_text_processor(
    logger: object, method_name: str, event_dict: dict
) -> dict:
    """Remove or truncate text fields from log events."""
    if "text" in event_dict:
        text = event_dict["text"]
        if isinstance(text, str) and len(text) > 50:
            event_dict["text"] = text[:50] + "...[REDACTED]"
    if "review_text" in event_dict:
        del event_dict["review_text"]
    return event_dict


def setup_logging(level: str = "INFO", log_full_text: bool = False) -> None:
    """Configure structured logging for the pipeline."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    if HAS_STRUCTLOG:
        processors: list = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
        ]

        if not log_full_text:
            processors.append(_redact_text_processor)

        processors.extend([
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
            if level.upper() == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ])

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )


class FallbackLogger:
    """Simple wrapper over standard logging with key-value kwarg formatting."""

    def __init__(self, name: str | None = None) -> None:
        self.logger = logging.getLogger(name or "absa")

    def _fmt(self, msg: str, **kwargs: Any) -> str:
        if kwargs:
            kv = " ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} | {kv}"
        return msg

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(self._fmt(msg, **kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(self._fmt(msg, **kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(self._fmt(msg, **kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(self._fmt(msg, **kwargs))


def get_logger(name: str | None = None) -> Any:
    """Get structured logger (or FallbackLogger if structlog is not present)."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return FallbackLogger(name)
