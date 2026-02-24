"""Tests for JSON and text log formatters."""

from __future__ import annotations

import json
import logging

from geohealth.logging_config import JSONFormatter, TextFormatter
from geohealth.services.request_context import request_id_var


def _make_record(msg: str = "hello", level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_json_output_structure():
    fmt = JSONFormatter()
    record = _make_record("test message")
    output = fmt.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["message"] == "test message"
    assert "timestamp" in data


def test_json_includes_request_id():
    fmt = JSONFormatter()
    token = request_id_var.set("abc123def456")
    try:
        record = _make_record("with id")
        output = fmt.format(record)
        data = json.loads(output)
        assert data["request_id"] == "abc123def456"
    finally:
        request_id_var.reset(token)


def test_json_excludes_empty_request_id():
    fmt = JSONFormatter()
    token = request_id_var.set("")
    try:
        record = _make_record("no id")
        output = fmt.format(record)
        data = json.loads(output)
        assert "request_id" not in data
    finally:
        request_id_var.reset(token)


def test_json_exception_formatting():
    fmt = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record("error")
        record.exc_info = sys.exc_info()
    output = fmt.format(record)
    data = json.loads(output)
    assert "exception" in data
    assert "ValueError: boom" in data["exception"]


def test_text_format_with_request_id():
    fmt = TextFormatter()
    token = request_id_var.set("aabbccdd1122")
    try:
        record = _make_record("hello text")
        output = fmt.format(record)
        assert "[aabbccdd1122]" in output
        assert "hello text" in output
    finally:
        request_id_var.reset(token)


def test_text_format_without_request_id():
    fmt = TextFormatter()
    token = request_id_var.set("")
    try:
        record = _make_record("no rid")
        output = fmt.format(record)
        assert "[" not in output or "test.logger" in output
        assert "no rid" in output
    finally:
        request_id_var.reset(token)
