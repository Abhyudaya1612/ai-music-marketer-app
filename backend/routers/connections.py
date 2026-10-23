"""Owner-scoped, read-only social account OAuth connections."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import settings
from ..core.auth import current_owner
from ..core.errors import ApiError
from ..database import get_db
from ..domain.models import PlatformConnection, PlatformOAuthState
from ..domain.schemas import OAuthStartOut, PlatformConnectionListOut, PlatformConnectionOut, PlatformProvider
from ..services.consent import has_active_consent
from ..services.platform_oauth import (
    PLATFORM_PROVIDERS,
    OAuthAccount,
    build_authorization_url,
    encrypt_token,
    exchange_authorization_code,
    provider_is_configured,
    provider_configuration,
)

router = APIRouter(prefix="/api/v1/connections", tags=["platform connections"])
STATE_LIFETIME = timedelta(minutes=10)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _connection_response(
    provider: PlatformProvider,
    connection: PlatformConnection | None,
) -> PlatformConnectionOut:
    configured = provider_is_configured(provider)
    expires_at = _as_utc(connection.access_token_expires_at) if connection else None
    if not configured:
        state = "not_configured"
    elif connection is None or connection.status != "connected":
        state = "not_connected"
    elif expires_at is not None and expires_at <= _utcnow():
        state = "expired"
    else:
        state = "connected"
    return PlatformConnectionOut(
        provider=provider,
        configured=configured,
        status=state,
        connected=state == "connected",
        account_id=connection.account_id if connection else None,
        account_name=connection.account_name if connection else None,
        granted_scopes=connection.granted_scopes_json or [] if connection else [],
        connected_at=connection.connected_at if connection else None,
        expires_at=expires_at,
    )


def _frontend_redirect(
    provider: PlatformProvider | None,
    result: str,
    reason: str | None = None,
) -> str:
    values = {"platform_connection": result}
    if provider:
        values["provider"] = provider
    if reason:
        values["reason"] = reason
    return f"{settings.frontend_url.rstrip('/')}/?{urlencode(values)}"


def _consume_state(
    db: Session,
    provider: PlatformProvider,
    state: str,
) -> PlatformOAuthState | None:
    state_hash = _state_hash(state)
    row = db.query(PlatformOAuthState).filter(
        PlatformOAuthState.state_hash == state_hash,
        PlatformOAuthState.provider == provider,
        PlatformOAuthState.consumed_at.is_(None),
        PlatformOAuthState.expires_at > _utcnow(),
    ).first()
    if row is None:
        return None
    result = db.execute(
        update(PlatformOAuthState)
        .where(
            PlatformOAuthState.state_hash == state_hash,
            PlatformOAuthState.consumed_at.is_(None),
            PlatformOAuthState.expires_at > _utcnow(),
        )
        .values(consumed_at=_utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return row


def _save_connection(
    db: Session,
    owner_id: str,
    provider: PlatformProvider,
    account: OAuthAccount,
) -> None:
    connection = db.query(PlatformConnection).filter(
        PlatformConnection.owner_id == owner_id,
        PlatformConnection.provider == provider,
    ).first()
    now = _utcnow()
    refresh_token = account.refresh_token
    if (
        refresh_token is None
        and connection is not None
        and connection.account_id == account.account_id
        and connection.refresh_token_encrypted is not None
    ):
        refresh_token_encrypted = connection.refresh_token_encrypted
    else:
        refresh_token_encrypted = encrypt_token(refresh_token) if refresh_token else None
    values = {
        "account_id": account.account_id,
        "account_name": account.account_name,
        "access_token_encrypted": encrypt_token(account.access_token),
        "refresh_token_encrypted": refresh_token_encrypted,
        "granted_scopes_json": account.granted_scopes,
        "access_token_expires_at": account.expires_at,
        "status": "connected",
        "connected_at": now,
        "updated_at": now,
        "disconnected_at": None,
    }
    if connection is None:
        db.add(PlatformConnection(owner_id=owner_id, provider=provider, **values))
    else:
        for field, value in values.items():
            setattr(connection, field, value)
    db.commit()


@router.get("", response_model=PlatformConnectionListOut)
def list_platform_connections(
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> PlatformConnectionListOut:
    rows = {
        row.provider: row
        for row in db.query(PlatformConnection).filter(PlatformConnection.owner_id == owner_id).all()
    }
    return PlatformConnectionListOut(
        items=[_connection_response(provider, rows.get(provider)) for provider in PLATFORM_PROVIDERS]
    )


@router.post("/{provider}/oauth/start", response_model=OAuthStartOut)
def start_platform_oauth(
    provider: PlatformProvider,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> OAuthStartOut:
    if not has_active_consent(db, owner_id, "platform_account_connection", None):
        raise ApiError(
            403,
            "CONSENT_REQUIRED",
            "Workspace platform-account connection consent is required.",
        )
    provider_configuration(provider)
    state = secrets.token_urlsafe(32)
    expires_at = _utcnow() + STATE_LIFETIME
    db.add(
        PlatformOAuthState(
            state_hash=_state_hash(state),
            owner_id=owner_id,
            provider=provider,
            expires_at=expires_at,
        )
    )
    db.commit()
    return OAuthStartOut(
        authorization_url=build_authorization_url(provider, state),
        expires_at=expires_at,
    )


@router.get("/oauth/callback/{provider}", include_in_schema=False)
def finish_platform_oauth(
    provider: PlatformProvider,
    state: Annotated[str | None, Query(max_length=200)] = None,
    code: Annotated[str | None, Query(max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=100)] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not state:
        return RedirectResponse(_frontend_redirect(provider, "failed", "invalid_state"), status_code=303)
    oauth_state = _consume_state(db, provider, state)
    if oauth_state is None:
        return RedirectResponse(_frontend_redirect(provider, "failed", "invalid_state"), status_code=303)
    if error:
        return RedirectResponse(_frontend_redirect(provider, "failed", "authorization_denied"), status_code=303)
    if not code:
        return RedirectResponse(_frontend_redirect(provider, "failed", "provider_error"), status_code=303)
    if not has_active_consent(db, oauth_state.owner_id, "platform_account_connection", None):
        return RedirectResponse(_frontend_redirect(provider, "failed", "consent_withdrawn"), status_code=303)
    try:
        account = exchange_authorization_code(provider, code)
    except ApiError as exc:
        reason = {
            "OAUTH_PROVIDER_TIMEOUT": "provider_timeout",
            "OAUTH_PROVIDER_UNAVAILABLE": "provider_unavailable",
            "OAUTH_ACCOUNT_UNAVAILABLE": "account_unavailable",
        }.get(exc.code, "provider_error")
        return RedirectResponse(_frontend_redirect(provider, "failed", reason), status_code=303)
    if not has_active_consent(db, oauth_state.owner_id, "platform_account_connection", None):
        return RedirectResponse(_frontend_redirect(provider, "failed", "consent_withdrawn"), status_code=303)
    _save_connection(db, oauth_state.owner_id, provider, account)
    return RedirectResponse(_frontend_redirect(provider, "connected"), status_code=303)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_platform(
    provider: PlatformProvider,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> Response:
    connection = db.query(PlatformConnection).filter(
        PlatformConnection.owner_id == owner_id,
        PlatformConnection.provider == provider,
    ).first()
    if connection is not None:
        connection.account_id = None
        connection.account_name = None
        connection.access_token_encrypted = None
        connection.refresh_token_encrypted = None
        connection.granted_scopes_json = []
        connection.access_token_expires_at = None
        connection.status = "disconnected"
        connection.disconnected_at = _utcnow()
        connection.updated_at = _utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
