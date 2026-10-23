from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_database_file = tempfile.NamedTemporaryFile(suffix="_platform.db", delete=False)
_database_path = _database_file.name
_database_file.close()
os.unlink(_database_path)
os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{Path(_database_path).as_posix()}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.fernet import Fernet  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import SecretStr  # noqa: E402
import pytest  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.domain.models import PlatformConnection, PlatformOAuthState, ConsentRecord  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routers import connections  # noqa: E402
from backend.services import platform_oauth  # noqa: E402
from backend.services.platform_oauth import OAuthAccount  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_platform_connections_db():
    """Clean up platform connections database before each test."""
    db = SessionLocal()
    try:
        # Clean all consent and connection records to avoid test pollution
        db.query(ConsentRecord).delete()
        db.query(PlatformOAuthState).delete()
        db.query(PlatformConnection).delete()
        db.commit()
    finally:
        db.close()
    yield


def _configure(monkeypatch, owner_id: str) -> str:
    monkeypatch.setattr(settings, "api_token", "test-platform-token")
    monkeypatch.setattr(settings, "auth_user_id", owner_id)
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    monkeypatch.setattr(settings, "token_encryption_key", SecretStr(Fernet.generate_key().decode()))
    for provider in ("youtube", "instagram", "facebook"):
        monkeypatch.setattr(settings, f"{provider}_oauth_client_id", f"{provider}-client")
        monkeypatch.setattr(settings, f"{provider}_oauth_client_secret", SecretStr(f"{provider}-secret"))
        monkeypatch.setattr(
            settings,
            f"{provider}_oauth_redirect_uri",
            f"http://localhost:8000/api/v1/connections/oauth/callback/{provider}",
        )
    return settings.token_encryption_key.get_secret_value()


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-platform-token"}


def _grant_connection_consent() -> dict:
    response = client.post(
        "/api/v1/consents",
        headers=_auth(),
        json={"consent_type": "platform_account_connection"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _state_from_start(provider: str = "youtube") -> tuple[str, str]:
    response = client.post(f"/api/v1/connections/{provider}/oauth/start", headers=_auth())
    assert response.status_code == 200, response.text
    values = parse_qs(urlparse(response.json()["authorization_url"]).query)
    return values["state"][0], response.json()["authorization_url"]


def test_platform_connection_requires_consent_and_requests_read_only_scopes(monkeypatch):
    owner_id = "platform-owner-consent-unique"
    _configure(monkeypatch, owner_id)

    denied = client.post("/api/v1/connections/youtube/oauth/start", headers=_auth())
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "CONSENT_REQUIRED"

    _grant_connection_consent()
    state, authorization_url = _state_from_start()
    query = parse_qs(urlparse(authorization_url).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/youtube.readonly"]
    assert query["state"] == [state]
    assert "youtube.upload" not in authorization_url

    db = SessionLocal()
    try:
        row = db.query(PlatformOAuthState).filter_by(owner_id=owner_id).one()
        assert row.state_hash != state
    finally:
        db.close()


def test_each_provider_requests_only_its_read_only_connection_scope(monkeypatch):
    _configure(monkeypatch, "platform-owner-scopes")
    expected = {
        "youtube": ("accounts.google.com", platform_oauth.YOUTUBE_SCOPE),
        "instagram": ("www.instagram.com", platform_oauth.INSTAGRAM_SCOPE),
        "facebook": ("www.facebook.com", platform_oauth.FACEBOOK_SCOPE),
    }
    for provider, (host, scope) in expected.items():
        url = platform_oauth.build_authorization_url(provider, "test-state")
        parsed = urlparse(url)
        values = parse_qs(parsed.query)
        assert host in parsed.netloc
        assert values["scope"] == [scope]
        assert values["state"] == ["test-state"]
        assert not any(term in scope.lower() for term in ("upload", "publish", "manage"))

    calls: list[tuple[str, str, dict | None, dict | None, bool, str | None]] = []
    responses = {
        "https://oauth2.googleapis.com/token": {"access_token": "yt-access", "refresh_token": "yt-refresh", "expires_in": 3600, "scope": platform_oauth.YOUTUBE_SCOPE},
        "https://www.googleapis.com/youtube/v3/channels": {"items": [{"id": "yt-channel", "snippet": {"title": "Artist channel"}}]},
        "https://api.instagram.com/oauth/access_token": {"access_token": "ig-short", "permissions": platform_oauth.INSTAGRAM_SCOPE, "user_id": "ig-123"},
        "https://graph.instagram.com/access_token": {"access_token": "ig-long", "expires_in": 5184000},
        "https://graph.instagram.com/me": {"user_id": "ig-123", "username": "artist"},
        f"https://graph.facebook.com/{settings.meta_graph_api_version}/oauth/access_token": {"access_token": "fb-token", "expires_in": 5184000, "scope": platform_oauth.FACEBOOK_SCOPE},
        f"https://graph.facebook.com/{settings.meta_graph_api_version}/me": {"id": "fb-123", "name": "Artist Profile"},
    }

    def fake_json_response(method, url, *, params=None, data=None, multipart=False, bearer_token=None):
        calls.append((method, url, params, data, multipart, bearer_token))
        if url.endswith("/oauth/access_token") and method == "GET" and url.startswith("https://graph.facebook.com/"):
            if params and "fb_exchange_token" in params:
                return {"access_token": "fb-long", "expires_in": 5184000, "scope": platform_oauth.FACEBOOK_SCOPE}
        return responses[url]

    monkeypatch.setattr(platform_oauth, "_json_response", fake_json_response)
    youtube = platform_oauth.exchange_authorization_code("youtube", "code")
    instagram = platform_oauth.exchange_authorization_code("instagram", "code")
    facebook = platform_oauth.exchange_authorization_code("facebook", "code")

    assert (youtube.account_id, youtube.account_name, youtube.refresh_token) == ("yt-channel", "Artist channel", "yt-refresh")
    assert (instagram.account_id, instagram.account_name) == ("ig-123", "artist")
    assert (facebook.account_id, facebook.account_name) == ("fb-123", "Artist Profile")
    assert any(call[4] for call in calls if call[1] == "https://api.instagram.com/oauth/access_token")
    assert all("youtube.upload" not in str(call) and "instagram_business_content_publish" not in str(call) for call in calls)


def test_oauth_callback_encrypts_tokens_and_is_one_time_owner_scoped(monkeypatch):
    owner_id = "platform-owner-success-unique"
    encryption_key = _configure(monkeypatch, owner_id)
    
    _grant_connection_consent()
    state, _ = _state_from_start("youtube")
    def fake_youtube_exchange(_provider, _code):
        assert _provider == "youtube"
        assert _code == "temporary-code"
        return OAuthAccount(
            account_id="channel-123",
            account_name="Test Channel",
            access_token="access-token-secret",
            refresh_token="refresh-token-secret",
            granted_scopes=[platform_oauth.YOUTUBE_SCOPE],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

    monkeypatch.setattr(connections, "exchange_authorization_code", fake_youtube_exchange)

    callback = client.get(
        "/api/v1/connections/oauth/callback/youtube",
        params={"state": state, "code": "temporary-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert "platform_connection=connected" in callback.headers["location"]

    listed = client.get("/api/v1/connections", headers=_auth())
    assert listed.status_code == 200
    youtube = next(item for item in listed.json()["items"] if item["provider"] == "youtube")
    assert youtube["status"] == "connected"
    assert youtube["account_name"] == "Test Channel"
    assert "access_token" not in str(youtube).lower()

    db = SessionLocal()
    try:
        saved = db.query(PlatformConnection).filter_by(owner_id=owner_id, provider="youtube").one()
        assert "access-token-secret" not in saved.access_token_encrypted
        assert "refresh-token-secret" not in saved.refresh_token_encrypted
        cipher = Fernet(encryption_key.encode("ascii"))
        assert cipher.decrypt(saved.access_token_encrypted.encode("ascii")).decode() == "access-token-secret"
        assert cipher.decrypt(saved.refresh_token_encrypted.encode("ascii")).decode() == "refresh-token-secret"
    finally:
        db.close()

    replay = client.get(
        "/api/v1/connections/oauth/callback/youtube",
        params={"state": state, "code": "temporary-code"},
        follow_redirects=False,
    )
    assert replay.status_code == 303
    assert "reason=invalid_state" in replay.headers["location"]

    removed = client.delete("/api/v1/connections/youtube", headers=_auth())
    assert removed.status_code == 204
    disconnected = client.get("/api/v1/connections", headers=_auth())
    youtube = next(item for item in disconnected.json()["items"] if item["provider"] == "youtube")
    assert youtube["status"] == "not_connected"

    monkeypatch.setattr(settings, "auth_user_id", "another-platform-owner")
    isolated = client.get("/api/v1/connections", headers=_auth())
    assert isolated.status_code == 200
    assert all(item["status"] == "not_connected" for item in isolated.json()["items"])


def test_withdrawing_connection_consent_deletes_tokens_and_pending_state(monkeypatch):
    owner_id = "platform-owner-withdraw-unique"
    _configure(monkeypatch, owner_id)
    
    consent = _grant_connection_consent()
    state, _ = _state_from_start("instagram")
    def fake_instagram_exchange(_provider, _code):
        assert _provider == "instagram"
        assert _code == "temporary-code"
        return OAuthAccount(
            account_id="instagram-123",
            account_name="artist",
            access_token="instagram-access-token",
            refresh_token=None,
            granted_scopes=[platform_oauth.INSTAGRAM_SCOPE],
            expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        )

    monkeypatch.setattr(connections, "exchange_authorization_code", fake_instagram_exchange)
    callback = client.get(
        "/api/v1/connections/oauth/callback/instagram",
        params={"state": state, "code": "temporary-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303

    withdrawn = client.post(
        f"/api/v1/consents/{consent['consent_id']}/withdraw",
        headers=_auth(),
    )
    assert withdrawn.status_code == 200, withdrawn.text
    listed = client.get("/api/v1/connections", headers=_auth())
    instagram = next(item for item in listed.json()["items"] if item["provider"] == "instagram")
    assert instagram["status"] == "not_connected"
    assert instagram["account_id"] is None

    db = SessionLocal()
    try:
        saved = db.query(PlatformConnection).filter_by(owner_id=owner_id, provider="instagram").one()
        pending = db.query(PlatformOAuthState).filter_by(owner_id=owner_id).one()
        assert saved.access_token_encrypted is None
        assert saved.refresh_token_encrypted is None
        assert pending.consumed_at is not None
    finally:
        db.close()


def test_pending_oauth_callback_is_invalidated_by_consent_withdrawal(monkeypatch):
    _configure(monkeypatch, "platform-owner-pending")
    consent = _grant_connection_consent()
    state, _ = _state_from_start("facebook")
    withdrawn = client.post(
        f"/api/v1/consents/{consent['consent_id']}/withdraw",
        headers=_auth(),
    )
    assert withdrawn.status_code == 200, withdrawn.text

    def unexpected_exchange(provider, code):
        pytest.fail(f"Unexpected provider exchange for {provider} with code {code}.")

    monkeypatch.setattr(connections, "exchange_authorization_code", unexpected_exchange)
    callback = client.get(
        "/api/v1/connections/oauth/callback/facebook",
        params={"state": state, "code": "temporary-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert "reason=invalid_state" in callback.headers["location"]
