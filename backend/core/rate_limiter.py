"""In-process rate limiting for API endpoints using slowapi."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_owner_aware_key(request: Request) -> str:
    """Get rate limit key from owner_id in state, or fall back to IP address."""
    # Try to get owner_id from current_owner() dependency result in state
    owner_id = getattr(request.state, "owner_id", None)
    if owner_id:
        return owner_id
    # Fall back to IP address for unauthenticated endpoints
    return get_remote_address(request)


# Initialize limiter with owner-aware key function
limiter = Limiter(
    key_func=get_owner_aware_key,
    default_limits=[],
    storage_uri="memory://",  # In-process memory store
)


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded by returning 429 with Retry-After header."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Parse the RateLimitExceeded message to extract retry info
    # Format is like: "10 per 1 minute" or "5 per 1 hour"
    retry_after = 60  # Default to 60 seconds
    try:
        # Try to extract a reasonable retry-after from the limit string
        # This is a simple heuristic; adjust as needed
        if "hour" in str(exc.detail).lower():
            retry_after = 3600
        elif "minute" in str(exc.detail).lower():
            retry_after = 60
    except Exception:
        pass
    
    # Log the violation
    key = getattr(request.state, "owner_id", getattr(request, "client", {}).host if hasattr(request, "client") else "unknown")
    logger.warning("rate_limit_violated", extra={
        "user_id": key,
        "endpoint": request.url.path,
    })
    
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "request_id": request_id,
                "details": [],
            }
        },
        headers={
            "X-Request-ID": request_id,
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": "10",
            "X-RateLimit-Reset": str(int((datetime.now(timezone.utc) + timedelta(seconds=retry_after)).timestamp())),
        },
    )
