"""Single-workspace bearer authentication for the local presentation build."""
from __future__ import annotations

import hmac
import logging

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import settings
from .errors import ApiError

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def current_owner(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if not settings.api_token:
        logger.warning("auth_attempt_failed", extra={"reason": "API_TOKEN_NOT_CONFIGURED"})
        raise ApiError(
            503,
            "AUTH_CONFIGURATION_MISSING",
            "Private API access is not configured. Set APP_API_TOKEN and restart the app.",
        )
    if credentials is None or not hmac.compare_digest(
        credentials.credentials, settings.api_token
    ):
        logger.warning("auth_attempt_failed", extra={"reason": "INVALID_OR_MISSING_TOKEN"})
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required.")
    
    owner_id = settings.auth_user_id
    # Store owner_id in request state for rate limiting and audit logging
    request.state.owner_id = owner_id
    return owner_id
