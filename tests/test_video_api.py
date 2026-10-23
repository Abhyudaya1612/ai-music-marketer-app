from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='_video.db')}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.domain.models import MediaAsset  # noqa: E402
from backend.main import app  # noqa: E402
from backend.services.storage import original_path, render_output_path  # noqa: E402

client = TestClient(app)


def _create_ready_source(tmp_path: Path, owner_id: str) -> tuple[str, str]:
    created = client.post("/api/v1/songs", headers=AUTH, json={"title": "Rendered Song", "artist_name": "Studio Artist"})
    assert created.status_code == 201, created.text
    song_id = created.json()["song_id"]
    consent = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "audio_processing", "song_id": song_id},
    )
    assert consent.status_code == 201, consent.text
    rights = client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "owned",
            "rights_confirmed": True,
        },
    )
    assert rights.status_code == 201, rights.text

    source_bytes = b"test source audio"
    asset_id = str(uuid.uuid4())
    source = original_path(asset_id)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(source_bytes)
    db = SessionLocal()
    try:
        db.add(
            MediaAsset(
                id=asset_id,
                song_id=song_id,
                owner_id=owner_id,
                filename="source.wav",
                status="ready",
                storage_key=asset_id,
                expected_size_bytes=len(source_bytes),
                size_bytes=len(source_bytes),
                checksum_sha256=hashlib.sha256(source_bytes).hexdigest(),
                actual_content_type="audio/wav",
                duration_seconds=2.0,
            )
        )
        db.commit()
    finally:
        db.close()
    return song_id, asset_id


AUTH = {"Authorization": "Bearer test-video-token"}


def test_video_render_api_requires_consent_and_returns_private_download(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-video-token")
    monkeypatch.setattr(settings, "auth_user_id", "video-owner-success")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    from backend.routers import v1
    from backend.services import job_runner
    from backend.services.video_rendering import build_scene_plan

    monkeypatch.setattr(v1, "renderer_capabilities", lambda: {"music_visualizer": True, "full_music_video": True})
    song_id, asset_id = _create_ready_source(tmp_path, settings.auth_user_id)
    payload = {"asset_id": asset_id, "render_format": "music_visualizer"}
    request_headers = {**AUTH, "Idempotency-Key": "video-render-success"}

    blocked = client.post(f"/api/v1/songs/{song_id}/video-renders", headers=request_headers, json=payload)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CONSENT_REQUIRED"
    granted = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "promotional_asset_generation", "song_id": song_id},
    )
    assert granted.status_code == 201

    def fake_render_motion_graphics(**kwargs):
        output = render_output_path(kwargs["render_id"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"mock validated mp4")
        kwargs["progress_callback"](50)
        return {
            "metadata": {
                "container": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac",
                "width": 1280,
                "height": 720,
                "aspect_ratio": "16:9",
                "duration_seconds": 2.0,
                "audio_present": True,
            },
            "size_bytes": output.stat().st_size,
            "checksum_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "scene_plan": build_scene_plan(2.0, kwargs["render_format"]),
            "render_settings": {"renderer": "test"},
            "provenance": {"model": None},
        }

    monkeypatch.setattr(job_runner, "render_motion_graphics", fake_render_motion_graphics)
    accepted = client.post(f"/api/v1/songs/{song_id}/video-renders", headers=request_headers, json=payload)
    assert accepted.status_code == 202, accepted.text
    render_id = accepted.json()["render_id"]
    completed = client.get(f"/api/v1/video-renders/{render_id}", headers=AUTH)
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    assert completed.json()["output_metadata"]["audio_present"] is True

    download = client.get(completed.json()["download_url"], headers=AUTH)
    assert download.status_code == 200
    assert download.headers["content-type"] == "video/mp4"
    assert download.headers["cache-control"] == "private, no-store"
    assert download.content == b"mock validated mp4"
    replay = client.post(f"/api/v1/songs/{song_id}/video-renders", headers=request_headers, json=payload)
    assert replay.status_code == 202
    assert replay.json()["render_id"] == render_id
    assert replay.json()["status"] == "succeeded"

    monkeypatch.setattr(settings, "auth_user_id", "video-owner-other")
    assert client.get(f"/api/v1/video-renders/{render_id}", headers=AUTH).status_code == 404
    assert client.get(completed.json()["download_url"], headers=AUTH).status_code == 404


def test_video_worker_rechecks_consent_before_starting_queued_render(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-video-token")
    monkeypatch.setattr(settings, "auth_user_id", "video-owner-withdrawn")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    from backend.routers import v1
    from backend.services import job_runner

    monkeypatch.setattr(v1, "renderer_capabilities", lambda: {"music_visualizer": True, "full_music_video": True})
    song_id, asset_id = _create_ready_source(tmp_path, settings.auth_user_id)
    granted = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "promotional_asset_generation", "song_id": song_id},
    )
    assert granted.status_code == 201
    monkeypatch.setattr(v1, "run_v1_job", lambda *_args, **_kwargs: None)

    accepted = client.post(
        f"/api/v1/songs/{song_id}/video-renders",
        headers={**AUTH, "Idempotency-Key": "video-render-withdrawn"},
        json={"asset_id": asset_id, "render_format": "full_music_video"},
    )
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "queued"

    withdrawn = client.post(
        f"/api/v1/consents/{granted.json()['consent_id']}/withdraw",
        headers=AUTH,
    )
    assert withdrawn.status_code == 200
    job_runner.run_v1_job(accepted.json()["job_id"])
    completed = client.get(accepted.json()["status_url"], headers=AUTH)
    assert completed.status_code == 200
    assert completed.json()["status"] == "failed"
    assert completed.json()["error"]["code"] == "CONSENT_REQUIRED"
