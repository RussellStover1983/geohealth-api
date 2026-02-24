"""Structured logging configuration (JSON and text formatters)."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone

from geohealth.services.request_context import get_request_id

# Attributes present on every LogRecord — used by JSONFormatter to filter extras.
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JSONFormatter(logging.Formatter):
    """Single-line JSON log output for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        entry: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        request_id = get_request_id()
        if request_id:
            entry["request_id"] = request_id

        # Include extra fields
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                entry[key] = value

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        return json.dumps(entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable text format with optional request ID prefix."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        ts = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S")

        request_id = get_request_id()
        rid_prefix = f"[{request_id[:12]}] " if request_id else ""

        line = f"{ts} {record.levelname:<8} {rid_prefix}{record.name} - {record.message}"

        if record.exc_info and record.exc_info[0] is not None:
            line += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return line


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    """Configure the root logger. Call once at startup."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output on reload
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root.addHandler(handler)
