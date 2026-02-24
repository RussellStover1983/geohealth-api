"""Request logging middleware (pure ASGI)."""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from geohealth.services.metrics import metrics
from geohealth.services.request_context import (
    generate_request_id,
    get_request_id,
    request_id_var,
)

logger = logging.getLogger("geohealth.access")


class RequestLoggingMiddleware:
    """Log ``method path status_code latency_ms`` for every request.

    Adds ``X-Response-Time-Ms`` and ``X-Request-ID`` headers to every
    response.  Collects per-request metrics (status codes, latency).

    Query params are intentionally NOT logged to avoid leaking API keys
    or PII in addresses.

    Implemented as pure ASGI middleware for minimal overhead.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Resolve or generate request ID
        incoming_id = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-request-id":
                incoming_id = header_value.decode("latin-1")
                break

        rid = incoming_id or generate_request_id()
        token = request_id_var.set(rid)

        start = time.perf_counter()
        status_code = 500  # default if we never see a response start

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-response-time-ms", str(elapsed_ms).encode())
                )
                headers.append(
                    (b"x-request-id", rid.encode())
                )
                message = {**message, "headers": headers}

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            path = scope.get("path", "")
            method = scope.get("method", "")
            logger.info(
                "%s %s %s %.2fms [%s]",
                method,
                path,
                status_code,
                elapsed_ms,
                get_request_id()[:12],
            )
            metrics.inc_request(status_code)
            metrics.record_latency(elapsed_ms)
            request_id_var.reset(token)
