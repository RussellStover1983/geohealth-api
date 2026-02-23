"""Request logging middleware (pure ASGI)."""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("geohealth.access")


class RequestLoggingMiddleware:
    """Log ``method path status_code latency_ms`` for every request.

    Adds an ``X-Response-Time-Ms`` header to every response.
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

        start = time.perf_counter()
        status_code = 500  # default if we never see a response start

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

                # Inject X-Response-Time-Ms header
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-response-time-ms", str(elapsed_ms).encode())
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
                "%s %s %s %.2fms",
                method,
                path,
                status_code,
                elapsed_ms,
            )
