"""End-to-end tests for publishing workflow."""
import os
import sys
import tempfile
from pathlib import Path

_database_file = tempfile.NamedTemporaryFile(suffix="_e2e_pub.db", delete=False)
_database_path = _database_file.name
_database_file.close()
os.unlink(_database_path)
os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{Path(_database_path).as_posix()}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal
from backend.config import settings
from backend.domain.models import (
    StudioSong,
    MediaAsset,
    VideoRender,
    AnalysisJob,
    PlatformConnection,
    new_id,
)


@pytest.fixture
def client(monkeypatch):
    """Get test client with auth token configured."""
    monkeypatch.setattr(settings, "api_token", "test_token")
    monkeypatch.setattr(settings, "auth_user_id", "test_owner_e2e")
    return TestClient(app)


@pytest.fixture
def test_owner():
    """Get test owner ID."""
    return "test_owner_e2e"


class TestPublishingWorkflow:
    """End-to-end publishing workflow tests."""

    def test_capabilities_includes_publishing_flags(self, client):
        """Test that capabilities endpoint includes publishing flags."""
        response = client.get("/api/v1/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert "ollama_available" in data["capabilities"]
        assert "youtube_publishing_available" in data["capabilities"]

    def test_queue_lyric_video_render_job(self, client, test_owner, monkeypatch):
        """Test queuing a lyric video render job."""
        monkeypatch.setattr(settings, "auth_user_id", test_owner)
        
        db = SessionLocal()
        try:
            # Clean up any existing media assets to avoid UNIQUE constraint on storage_key
            db.query(MediaAsset).filter(
                MediaAsset.owner_id == test_owner,
                MediaAsset.storage_key == "test_key"
            ).delete()
            db.commit()
            
            # Create test data
            song = StudioSong(
                id=new_id(),
                owner_id=test_owner,
                title="Test Song",
            )
            asset = MediaAsset(
                id=new_id(),
                song_id=song.id,
                owner_id=test_owner,
                asset_kind="audio_original",
                filename="test.mp3",
                storage_key="test_key",
                expected_size_bytes=1000,
                status="ready",
            )
            render = VideoRender(
                id=new_id(),
                owner_id=test_owner,
                song_id=song.id,
                asset_id=asset.id,
                job_id=new_id(),
                render_format="music_visualizer",
                status="succeeded",
                render_settings_json={},
                scene_plan_json=[],
                provenance_json={},
            )
            db.add_all([song, asset, render])
            db.commit()

            response = client.post(
                f"/api/v1/video/{render.id}/generate-lyric-video",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["task_type"] == "lyric_video_render"
            assert data["status"] == "queued"
            assert "job_id" in data

        finally:
            db.close()

    def test_queue_youtube_publish_job(self, client, test_owner, monkeypatch):
        """Test queuing a YouTube publish job."""
        monkeypatch.setattr(settings, "auth_user_id", test_owner)
        
        db = SessionLocal()
        try:
            # Clean up any existing connections for test_owner to avoid UNIQUE constraint
            db.query(PlatformConnection).filter(
                PlatformConnection.owner_id == test_owner,
                PlatformConnection.provider == "youtube"
            ).delete()
            db.commit()
            
            # Create test data
            song = StudioSong(
                id=new_id(),
                owner_id=test_owner,
                title="Test Song",
            )
            render = VideoRender(
                id=new_id(),
                owner_id=test_owner,
                song_id=song.id,
                asset_id=new_id(),
                job_id=new_id(),
                render_format="music_visualizer",
                status="succeeded",
                render_settings_json={},
                scene_plan_json=[],
                provenance_json={},
            )
            conn = PlatformConnection(
                id=new_id(),
                owner_id=test_owner,
                provider="youtube",
                account_id="test_account",
                access_token_encrypted="encrypted_token",
                status="connected",
            )
            db.add_all([song, render, conn])
            db.commit()

            response = client.post(
                f"/api/v1/video/{render.id}/publish-youtube",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["task_type"] == "youtube_publish"
            assert data["status"] == "queued"
            assert "job_id" in data

        finally:
            db.close()

    def test_publish_requires_succeeded_render(self, client, test_owner, monkeypatch):
        """Test that YouTube publish requires succeeded render."""
        monkeypatch.setattr(settings, "auth_user_id", test_owner)
        
        db = SessionLocal()
        try:
            render = VideoRender(
                id=new_id(),
                owner_id=test_owner,
                song_id=new_id(),
                asset_id=new_id(),
                job_id=new_id(),
                render_format="music_visualizer",
                status="queued",  # Not succeeded
                render_settings_json={},
                scene_plan_json=[],
                provenance_json={},
            )
            db.add(render)
            db.commit()

            response = client.post(
                f"/api/v1/video/{render.id}/publish-youtube",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 409

        finally:
            db.close()

    def test_publish_requires_youtube_connection(self, client, test_owner, monkeypatch):
        """Test that YouTube publish requires connected account."""
        monkeypatch.setattr(settings, "auth_user_id", test_owner)
        
        db = SessionLocal()
        try:
            # Clean up any existing connections for this owner
            db.query(PlatformConnection).filter(
                PlatformConnection.owner_id == test_owner,
                PlatformConnection.provider == "youtube"
            ).delete()
            db.commit()
            
            render = VideoRender(
                id=new_id(),
                owner_id=test_owner,
                song_id=new_id(),
                asset_id=new_id(),
                job_id=new_id(),
                render_format="music_visualizer",
                status="succeeded",
                render_settings_json={},
                scene_plan_json=[],
                provenance_json={},
            )
            db.add(render)
            db.commit()

            response = client.post(
                f"/api/v1/video/{render.id}/publish-youtube",
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 403

        finally:
            db.close()

    @patch("os.path.exists")
    @patch("backend.services.job_runner.publish_to_youtube")
    @patch("backend.services.job_runner.generate_metadata")
    @patch("backend.services.job_runner.decrypt_token")
    def test_workflow_metadata_to_youtube(
        self, mock_decrypt, mock_metadata, mock_publish, mock_exists, client, test_owner, monkeypatch
    ):
        """Test that metadata flows through to YouTube upload."""
        monkeypatch.setattr(settings, "auth_user_id", test_owner)
        
        mock_decrypt.return_value = "decrypted_token"
        mock_exists.return_value = True
        mock_metadata.return_value = MagicMock(
            title="Generated Title",
            description="Generated Description",
            tags=["music"],
        )
        mock_publish.return_value = MagicMock(
            video_id="dQw4w9WgXcQ",
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        )

        db = SessionLocal()
        try:
            # Clean up any existing connections for test_owner
            db.query(PlatformConnection).filter(
                PlatformConnection.owner_id == test_owner,
                PlatformConnection.provider == "youtube"
            ).delete()
            db.commit()
            
            song = StudioSong(
                id=new_id(),
                owner_id=test_owner,
                title="Test Song",
            )
            render = VideoRender(
                id=new_id(),
                owner_id=test_owner,
                song_id=song.id,
                asset_id=new_id(),
                job_id=new_id(),
                render_format="music_visualizer",
                status="succeeded",
                render_settings_json={},
                scene_plan_json=[],
                provenance_json={},
            )
            conn = PlatformConnection(
                id=new_id(),
                owner_id=test_owner,
                provider="youtube",
                account_id="test_account",
                access_token_encrypted="encrypted_token",
                status="connected",
            )
            job = AnalysisJob(
                id=new_id(),
                owner_id=test_owner,
                task_type="youtube_publish",
                subject_id=render.id,
                status="queued",
            )
            db.add_all([song, render, conn, job])
            db.commit()

            # Simulate job runner
            from backend.services.job_runner import _youtube_publish_job

            job.status = "running"
            db.commit()

            _youtube_publish_job(db, job)

            # Verify metadata was generated and passed to YouTube
            mock_metadata.assert_called_once()
            mock_publish.assert_called_once()

            # Verify render was updated
            render_updated = db.query(VideoRender).filter(
                VideoRender.id == render.id
            ).first()
            assert render_updated.publish_status == "published"
            assert "youtube" in render_updated.platform_urls

        finally:
            db.close()
