"""OAuth configuration, provider exchanges, and encrypted token storage."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from ..config import settings
from ..core.errors import ApiError

PlatformProvider = Literal["youtube", "instagram", "facebook"]
PLATFORM_PROVIDERS: tuple[PlatformProvider, ...] = ("youtube", "instagram", "facebook")
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"  # Allows full YouTube API access including uploads
INSTAGRAM_SCOPE = "instagram_business_basic"
FACEBOOK_SCOPE = "public_profile"


@dataclass(frozen=True)
class OAuthConfiguration:
    provider: PlatformProvider
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class OAuthAccount:
    account_id: str
    account_name: str
    access_token: str
    refresh_token: str | None
    granted_scopes: list[str]
    expires_at: datetime | None


def _configuration(provider: PlatformProvider) -> OAuthConfiguration | None:
    if provider == "youtube":
        values = (
            settings.youtube_oauth_client_id,
            settings.youtube_oauth_client_secret.get_secret_value(),
            settings.youtube_oauth_redirect_uri,
        )
    elif provider == "instagram":
        values = (
            settings.instagram_oauth_client_id,
            settings.instagram_oauth_client_secret.get_secret_value(),
            settings.instagram_oauth_redirect_uri,
        )
    else:
        values = (
            settings.facebook_oauth_client_id,
            settings.facebook_oauth_client_secret.get_secret_value(),
            settings.facebook_oauth_redirect_uri,
        )
    if not all(value.strip() for value in values):
        return None
    return OAuthConfiguration(provider, values[0], values[1], values[2])


def _cipher() -> Fernet:
    key = settings.token_encryption_key.get_secret_value().strip()
    if not key:
        raise ApiError(
            503,
            "TOKEN_ENCRYPTION_NOT_CONFIGURED",
            "Set APP_TOKEN_ENCRYPTION_KEY before connecting a platform account.",
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ApiError(
            503,
            "TOKEN_ENCRYPTION_KEY_INVALID",
            "APP_TOKEN_ENCRYPTION_KEY must be a valid Fernet key.",
        ) from exc


def provider_is_configured(provider: PlatformProvider) -> bool:
    if _configuration(provider) is None:
        return False
    try:
        _cipher()
    except ApiError:
        return False
    return True


def provider_configuration(provider: PlatformProvider) -> OAuthConfiguration:
    config = _configuration(provider)
    if config is None:
        raise ApiError(
            503,
            "OAUTH_PROVIDER_NOT_CONFIGURED",
            f"{provider.capitalize()} OAuth credentials and callback URL are not configured.",
        )
    _cipher()
    return config


def encrypt_token(token: str) -> str:
    return _cipher().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_token(token: str) -> str:
    try:
        return _cipher().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError) as exc:
        raise ApiError(
            503,
            "TOKEN_DECRYPTION_FAILED",
            "A stored platform token could not be decrypted. Verify APP_TOKEN_ENCRYPTION_KEY.",
        ) from exc


def _provider_url(path: str) -> str:
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}/{path.lstrip('/')}"


def build_authorization_url(provider: PlatformProvider, state: str) -> str:
    config = provider_configuration(provider)
    if provider == "youtube":
        endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        values = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": YOUTUBE_SCOPE,
            "access_type": "offline",
            "prompt": "consent select_account",
            "state": state,
        }
    elif provider == "instagram":
        endpoint = "https://www.instagram.com/oauth/authorize"
        values = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": INSTAGRAM_SCOPE,
            "state": state,
        }
    else:
        endpoint = f"https://www.facebook.com/{settings.meta_graph_api_version}/dialog/oauth"
        values = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": FACEBOOK_SCOPE,
            "state": state,
        }
    return f"{endpoint}?{urlencode(values)}"


def _json_response(
    method: Literal["GET", "POST"],
    url: str,
    *,
    params: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    multipart: bool = False,
    bearer_token: str | None = None,
) -> dict:
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.request(
                method,
                url,
                params=params,
                data=None if multipart else data,
                files={key: (None, value) for key, value in data.items()} if multipart and data else None,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise ApiError(502, "OAUTH_PROVIDER_TIMEOUT", "The platform OAuth service timed out.") from exc
    except httpx.RequestError as exc:
        raise ApiError(502, "OAUTH_PROVIDER_UNAVAILABLE", "The platform OAuth service could not be reached.") from exc
    if response.is_error:
        raise ApiError(502, "OAUTH_PROVIDER_ERROR", "The platform did not complete account authorization.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError(502, "OAUTH_PROVIDER_RESPONSE_INVALID", "The platform returned an invalid authorization response.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise ApiError(502, "OAUTH_PROVIDER_ERROR", "The platform did not complete account authorization.")
    return payload


def _required_string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ApiError(502, "OAUTH_PROVIDER_RESPONSE_INVALID", "The platform returned incomplete account data.")
    return value


def _expiry(payload: dict) -> datetime | None:
    seconds = payload.get("expires_in")
    if seconds is None:
        return None
    try:
        seconds = int(seconds)
    except (TypeError, ValueError) as exc:
        raise ApiError(502, "OAUTH_PROVIDER_RESPONSE_INVALID", "The platform returned an invalid token lifetime.") from exc
    if seconds <= 0:
        raise ApiError(502, "OAUTH_PROVIDER_RESPONSE_INVALID", "The platform returned an expired token.")
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _scopes(value: object, fallback: str, delimiter: str = " ") -> list[str]:
    if not isinstance(value, str) or not value.strip():
        value = fallback
    return sorted({scope.strip() for scope in value.split(delimiter) if scope.strip()})


def exchange_authorization_code(
    provider: PlatformProvider,
    code: str,
) -> OAuthAccount:
    config = provider_configuration(provider)
    if provider == "youtube":
        token_payload = _json_response(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri,
            },
        )
        access_token = _required_string(token_payload, "access_token")
        channels = _json_response(
            "GET",
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "id,snippet", "mine": "true", "maxResults": "50"},
            bearer_token=access_token,
        )
        items = channels.get("items")
        if not isinstance(items, list) or not items:
            raise ApiError(409, "OAUTH_ACCOUNT_UNAVAILABLE", "No YouTube channel was available for this Google account.")
        channel = items[0]
        if not isinstance(channel, dict) or not isinstance(channel.get("snippet"), dict):
            raise ApiError(502, "OAUTH_PROVIDER_RESPONSE_INVALID", "YouTube returned incomplete channel data.")
        return OAuthAccount(
            account_id=_required_string(channel, "id"),
            account_name=_required_string(channel["snippet"], "title"),
            access_token=access_token,
            refresh_token=token_payload.get("refresh_token"),
            granted_scopes=_scopes(token_payload.get("scope"), YOUTUBE_SCOPE),
            expires_at=_expiry(token_payload),
        )

    if provider == "instagram":
        short_lived = _json_response(
            "POST",
            "https://api.instagram.com/oauth/access_token",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": config.redirect_uri,
                "code": code,
            },
            multipart=True,
        )
        short_token = _required_string(short_lived, "access_token")
        long_lived = _json_response(
            "GET",
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": config.client_secret,
                "access_token": short_token,
            },
        )
        access_token = _required_string(long_lived, "access_token")
        account = _json_response(
            "GET",
            "https://graph.instagram.com/me",
            params={"fields": "user_id,username", "access_token": access_token},
        )
        return OAuthAccount(
            account_id=_required_string(account, "user_id"),
            account_name=_required_string(account, "username"),
            access_token=access_token,
            refresh_token=None,
            granted_scopes=_scopes(short_lived.get("permissions"), INSTAGRAM_SCOPE, ","),
            expires_at=_expiry(long_lived),
        )

    short_lived = _json_response(
        "GET",
        _provider_url("oauth/access_token"),
        params={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
    )
    short_token = _required_string(short_lived, "access_token")
    long_lived = _json_response(
        "GET",
        _provider_url("oauth/access_token"),
        params={
            "grant_type": "fb_exchange_token",
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "fb_exchange_token": short_token,
        },
    )
    access_token = _required_string(long_lived, "access_token")
    account = _json_response(
        "GET",
        _provider_url("me"),
        params={"fields": "id,name"},
        bearer_token=access_token,
    )
    return OAuthAccount(
        account_id=_required_string(account, "id"),
        account_name=_required_string(account, "name"),
        access_token=access_token,
        refresh_token=None,
        granted_scopes=_scopes(long_lived.get("scope"), FACEBOOK_SCOPE),
        expires_at=_expiry(long_lived),
    )
