"""Request correlation ID via contextvars."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def generate_request_id() -> str:
    """Return a new 32-character hex request ID."""
    return uuid.uuid4().hex


def get_request_id() -> str:
    """Read the current request ID from the contextvar."""
    return request_id_var.get()
