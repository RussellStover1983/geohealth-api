"""Webhook dispatch service — delivers events to subscriber callback URLs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from geohealth.config import settings

logger = logging.getLogger(__name__)


def _sign_payload(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _matches_filters(event_type: str, data: dict, filters: dict | None) -> bool:
    """Check if an event matches a subscription's filters."""
    if not filters:
        return True

    # State filter
    state_fips_filter = filters.get("state_fips")
    if state_fips_filter and isinstance(state_fips_filter, list):
        data_state = data.get("state_fips")
        if data_state and data_state not in state_fips_filter:
            return False

    # GEOID filter
    geoids_filter = filters.get("geoids")
    if geoids_filter and isinstance(geoids_filter, list):
        data_geoid = data.get("geoid")
        if data_geoid and data_geoid not in geoids_filter:
            return False

    # Threshold filter (for threshold.exceeded events)
    if event_type == "threshold.exceeded":
        thresholds = filters.get("thresholds")
        if thresholds and isinstance(thresholds, dict):
            for metric, condition in thresholds.items():
                if not isinstance(condition, dict):
                    continue
                op = condition.get("operator", ">")
                threshold_val = condition.get("value")
                actual_val = data.get(metric)
                if actual_val is None or threshold_val is None:
                    continue
                if op == ">" and not (actual_val > threshold_val):
                    return False
                elif op == ">=" and not (actual_val >= threshold_val):
                    return False
                elif op == "<" and not (actual_val < threshold_val):
                    return False
                elif op == "<=" and not (actual_val <= threshold_val):
                    return False

    return True


async def _deliver_with_retry(
    sub,
    body: bytes,
    headers: dict[str, str],
) -> bool:
    """Attempt delivery to a single subscription with exponential backoff.

    Returns True if delivered successfully, False otherwise.
    """
    max_retries = settings.webhook_max_retries
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
                resp = await client.post(sub.url, content=body, headers=headers)
            if resp.status_code < 400:
                logger.info(
                    "Webhook %d delivered to %s (status %d, attempt %d)",
                    sub.id, sub.url, resp.status_code, attempt + 1,
                )
                return True
            # Server error (5xx) — retry; client error (4xx) — don't retry
            if resp.status_code >= 500 and attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(
                    "Webhook %d to %s returned %d, retrying in %ds (attempt %d/%d)",
                    sub.id, sub.url, resp.status_code, wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
                continue
            logger.warning(
                "Webhook %d delivery to %s failed (status %d, attempt %d/%d)",
                sub.id, sub.url, resp.status_code, attempt + 1, max_retries,
            )
            return False
        except Exception:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(
                    "Webhook %d to %s raised exception, retrying in %ds (attempt %d/%d)",
                    sub.id, sub.url, wait, attempt + 1, max_retries,
                    exc_info=True,
                )
                await asyncio.sleep(wait)
            else:
                logger.exception(
                    "Webhook %d to %s failed after %d attempts",
                    sub.id, sub.url, max_retries,
                )
                return False
    return False


async def dispatch_event(
    event_type: str,
    data: dict[str, Any],
    subscriptions: list,
) -> dict[str, int]:
    """Deliver a webhook event to all matching subscriptions.

    Args:
        event_type: Event type string (e.g., "data.updated").
        data: Event payload data.
        subscriptions: List of WebhookSubscription ORM instances.

    Returns:
        Dict with "delivered" and "failed" counts.
    """
    delivered = 0
    failed = 0

    for sub in subscriptions:
        if not sub.active:
            continue
        if event_type not in (sub.events or []):
            continue
        if not _matches_filters(event_type, data, sub.filters):
            continue

        payload = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        body = json.dumps(payload).encode()

        headers = {"Content-Type": "application/json"}
        if sub.secret:
            headers["X-Webhook-Signature"] = f"sha256={_sign_payload(body, sub.secret)}"

        if await _deliver_with_retry(sub, body, headers):
            delivered += 1
        else:
            failed += 1

    return {"delivered": delivered, "failed": failed}
