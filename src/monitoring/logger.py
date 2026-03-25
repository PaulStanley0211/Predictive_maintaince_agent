import json
import logging
import sys

from src.config.settings import settings

_PLACEHOLDER_KEYS = {"", "your-key-here"}


class _JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON string for the given log record."""
        self.formatTime(record)  # populates record.asctime
        return json.dumps(
            {
                "ts": record.asctime,
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


def setup_logging() -> None:
    """Configure root logging: readable console output in dev, JSON in production."""
    if settings.environment == "production":
        formatter: logging.Formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


def setup_langfuse():
    """Initialise and return a Langfuse client, or None if keys are not configured."""
    if settings.langfuse_secret_key in _PLACEHOLDER_KEYS or settings.langfuse_public_key in _PLACEHOLDER_KEYS:
        return None
    from langfuse import Langfuse  # noqa: PLC0415

    return Langfuse(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
    )


logger = get_logger(__name__)
