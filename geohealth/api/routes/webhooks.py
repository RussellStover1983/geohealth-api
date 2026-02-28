"""CRUD endpoints for webhook subscriptions: /v1/webhooks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geohealth.api.auth import require_api_key
from geohealth.api.dependencies import get_db
from geohealth.api.schemas import (
    ErrorResponse,
    WebhookCreate,
    WebhookListResponse,
    WebhookResponse,
)
from geohealth.config import settings
from geohealth.db.models import WebhookSubscription
from geohealth.services.rate_limiter import rate_limiter

router = APIRouter(prefix="/v1", tags=["webhooks"])

VALID_EVENTS = {"data.updated", "threshold.exceeded"}


def _serialize_webhook(sub: WebhookSubscription) -> dict:
    """Convert a WebhookSubscription ORM instance to a response dict."""
    return {
        "id": sub.id,
        "url": sub.url,
        "events": sub.events,
        "filters": sub.filters,
        "active": sub.active,
        "created_at": sub.created_at.isoformat() if sub.created_at else "",
    }


@router.post(
    "/webhooks",
    summary="Create a webhook subscription",
    description=(
        "Register a callback URL to receive notifications when data changes "
        "or metric thresholds are exceeded.\n\n"
        "**Events**:\n"
        "- `data.updated` — fired when ETL refreshes tract data\n"
        "- `threshold.exceeded` — fired when a metric crosses a defined threshold\n\n"
        "**Filters** (optional):\n"
        "- `state_fips` — list of state FIPS codes to monitor\n"
        "- `geoids` — list of specific tract GEOIDs\n"
        "- `thresholds` — dict of metric thresholds, e.g. "
        '`{"poverty_rate": {"operator": ">", "value": 20}}`'
    ),
    response_model=WebhookResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid event type or limit exceeded"},
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def create_webhook(
    body: WebhookCreate,
    response: Response,
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Create a new webhook subscription."""

    # --- rate limit ----------------------------------------------------------
    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # --- validate events -----------------------------------------------------
    invalid = set(body.events) - VALID_EVENTS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event types: {', '.join(sorted(invalid))}. "
            f"Valid: {', '.join(sorted(VALID_EVENTS))}",
        )

    # --- check per-key limit -------------------------------------------------
    count_result = await session.execute(
        select(WebhookSubscription)
        .where(
            WebhookSubscription.api_key_hash == api_key,
            WebhookSubscription.active.is_(True),
        )
    )
    existing = len(count_result.scalars().all())
    if existing >= settings.webhook_max_per_key:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.webhook_max_per_key} active webhooks per API key.",
        )

    # --- create subscription -------------------------------------------------
    sub = WebhookSubscription(
        url=body.url,
        api_key_hash=api_key,
        events=body.events,
        filters=body.filters,
        secret=body.secret,
        active=True,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    response.status_code = 201
    return _serialize_webhook(sub)


@router.get(
    "/webhooks",
    summary="List webhook subscriptions",
    description="List all webhook subscriptions for the authenticated API key.",
    response_model=WebhookListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def list_webhooks(
    response: Response,
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """List all webhooks for the authenticated key."""

    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    result = await session.execute(
        select(WebhookSubscription)
        .where(WebhookSubscription.api_key_hash == api_key)
        .order_by(WebhookSubscription.id)
    )
    subs = result.scalars().all()

    return {
        "total": len(subs),
        "webhooks": [_serialize_webhook(s) for s in subs],
    }


@router.get(
    "/webhooks/{webhook_id}",
    summary="Get a webhook subscription",
    description="Get details of a specific webhook subscription.",
    response_model=WebhookResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Webhook not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def get_webhook(
    response: Response,
    webhook_id: int = Path(..., description="Webhook subscription ID"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Get a specific webhook by ID."""

    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    result = await session.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.api_key_hash == api_key,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Webhook not found.")

    return _serialize_webhook(sub)


@router.delete(
    "/webhooks/{webhook_id}",
    summary="Delete a webhook subscription",
    description="Permanently delete a webhook subscription.",
    status_code=204,
    responses={
        401: {"model": ErrorResponse, "description": "Missing API key"},
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Webhook not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def delete_webhook(
    response: Response,
    webhook_id: int = Path(..., description="Webhook subscription ID"),
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    """Delete a webhook subscription."""

    allowed, rl_headers = rate_limiter.is_allowed(api_key)
    for hdr, val in rl_headers.items():
        response.headers[hdr] = val
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    result = await session.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.id == webhook_id,
            WebhookSubscription.api_key_hash == api_key,
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Webhook not found.")

    await session.delete(sub)
    await session.commit()
    return Response(status_code=204)
