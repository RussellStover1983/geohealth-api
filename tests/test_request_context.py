"""Tests for request ID generation and contextvar propagation."""

from __future__ import annotations

import re

from geohealth.services.request_context import (
    generate_request_id,
    get_request_id,
    request_id_var,
)


def test_generate_request_id_is_hex():
    rid = generate_request_id()
    assert re.fullmatch(r"[0-9a-f]{32}", rid), f"Not 32 hex chars: {rid}"


def test_generate_request_id_unique():
    ids = {generate_request_id() for _ in range(100)}
    assert len(ids) == 100


def test_default_is_empty():
    # Reset to default by reading without prior set
    token = request_id_var.set("")
    try:
        assert get_request_id() == ""
    finally:
        request_id_var.reset(token)


def test_set_and_get():
    token = request_id_var.set("abc123")
    try:
        assert get_request_id() == "abc123"
    finally:
        request_id_var.reset(token)
