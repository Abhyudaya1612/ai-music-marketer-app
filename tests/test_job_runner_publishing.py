"""Tests for job runner publishing functionality."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from backend.domain.models import (
    AnalysisJob,
    VideoRender,
    StudioSong,
    MediaAsset,
    PlatformConnection,
    new_id,
)
from backend.services.job_runner import (
    _lyric_video_render_job,
    _youtube_publish_job,
    _classify_error,
)
from backend.services.youtube_publisher import YouTubePublishError


class TestErrorClassification:
    """Test error classification for retry logic."""

    def test_recoverable_errors(self):
        """Test errors that should be retried."""
        recoverable = [
            "YT_QUOTA_EXCEEDED",
            "YT_SERVER_ERROR",
            "RENDER_TIMEOUT",
            "FFMPEG_RENDER_FAILED",
        ]
        for error_code in recoverable:
            assert _classify_error(error_code) is True

    def test_permanent_errors(self):
        """Test errors that should not be retried."""
        permanent = [
            "YT_AUTH_FAILED",
            "YT_INVALID_VIDEO",
            "YT_NOT_CONNECTED",
            "RESOURCE_NOT_FOUND",
        ]
        for error_code in permanent:
            assert _classify_error(error_code) is False

    @patch("os.path.exists")
    @patch("backend.services.job_runner.publish_to_youtube")
    @patch("backend.services.job_runner.generate_metadata")
    @patch("backend.services.job_runner.decrypt_token")
    def test_youtube_publish_retryable_error(
        self, mock_decrypt, mock_metadata, mock_publish, mock_exists, db: Session
    ):
        """Test that retryable errors set job status to failed_retryable."""
        mock_decrypt.return_value = "decrypted_token"
        mock_exists.return_value = True
        mock_metadata.return_value = MagicMock(
            title="Test Song",
            description="Test Description",
            tags=["music"],
        )
        # Simulate a retryable error
        mock_publish.side_effect = YouTubePublishError(
            "YT_QUOTA_EXCEEDED",
            "Quota exceeded",
            is_recoverable=True,
        )

        song = StudioSong(
            id=new_id(),
            owner_id="test_owner",
            title="Test Song",
        )
        db.add(song)

        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=song.id,
            asset_id=new_id(),
            job_id=new_id(),
            render_format="music_visualizer",
            status="succeeded",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(render)

        conn = PlatformConnection(
            id=new_id(),
            owner_id="test_owner",
            provider="youtube",
            account_id="test_account",
            account_name="Test Account",
            access_token_encrypted="encrypted_token",
            granted_scopes_json=["youtube"],
            status="connected",
        )
        db.add(conn)

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        # The job should raise but set status to failed_retryable
        with pytest.raises(YouTubePublishError):
            _youtube_publish_job(db, job)

        job_updated = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()
        assert job_updated.status == "failed_retryable"
        assert job_updated.error_code == "YT_QUOTA_EXCEEDED"

    @patch("os.path.exists")
    @patch("backend.services.job_runner.publish_to_youtube")
    @patch("backend.services.job_runner.generate_metadata")
    @patch("backend.services.job_runner.decrypt_token")
    def test_youtube_publish_permanent_error(
        self, mock_decrypt, mock_metadata, mock_publish, mock_exists, db: Session
    ):
        """Test that permanent errors set job status to failed."""
        mock_decrypt.return_value = "decrypted_token"
        mock_exists.return_value = True
        mock_metadata.return_value = MagicMock(
            title="Test Song",
            description="Test Description",
            tags=["music"],
        )
        # Simulate a permanent error
        mock_publish.side_effect = YouTubePublishError(
            "YT_AUTH_FAILED",
            "Auth failed",
            is_recoverable=False,
        )

        song = StudioSong(
            id=new_id(),
            owner_id="test_owner",
            title="Test Song",
        )
        db.add(song)

        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=song.id,
            asset_id=new_id(),
            job_id=new_id(),
            render_format="music_visualizer",
            status="succeeded",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(render)

        conn = PlatformConnection(
            id=new_id(),
            owner_id="test_owner",
            provider="youtube",
            account_id="test_account",
            account_name="Test Account",
            access_token_encrypted="encrypted_token",
            granted_scopes_json=["youtube"],
            status="connected",
        )
        db.add(conn)

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        # The job should not raise for permanent errors
        _youtube_publish_job(db, job)

        job_updated = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()
        assert job_updated.status == "failed"
        assert job_updated.error_code == "YT_AUTH_FAILED"


class TestLyricVideoRenderJob:
    """Test lyric video render job execution."""

    def test_lyric_video_render_job_missing_render(self, db: Session):
        """Test job fails gracefully when render not found."""
        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="lyric_video_render",
            subject_id="nonexistent_render",
            status="running",
        )

        _lyric_video_render_job(db, job)

        assert job.status == "failed"
        assert job.error_code == "RESOURCE_NOT_FOUND"

    def test_lyric_video_render_job_missing_asset(self, db: Session):
        """Test job fails when asset not found."""
        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=new_id(),
            asset_id="nonexistent_asset",
            job_id=new_id(),
            render_format="music_visualizer",
            status="queued",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(render)

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="lyric_video_render",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        _lyric_video_render_job(db, job)

        render_updated = db.query(VideoRender).filter(VideoRender.id == render.id).first()
        assert render_updated.status == "failed"

    @patch("backend.services.job_runner.render_lyric_video")
    def test_lyric_video_render_job_success(self, mock_render, db: Session):
        """Test successful lyric video render job."""
        mock_render.return_value = {
            "video_id": "test_video",
            "duration_seconds": 120,
            "output_path": "/tmp/output.mp4",
        }

        song = StudioSong(
            id=new_id(),
            owner_id="test_owner",
            title="Test Song",
        )
        asset = MediaAsset(
            id=new_id(),
            song_id=song.id,
            owner_id="test_owner",
            asset_kind="audio_original",
            filename="test.mp3",
            storage_key=new_id(),
            expected_size_bytes=1000,
            status="ready",
            duration_seconds=120,
        )
        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=song.id,
            asset_id=asset.id,
            job_id=new_id(),
            render_format="music_visualizer",
            status="queued",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(song)
        db.add(asset)
        db.add(render)

        job = AnalysisJob(
            id=render.job_id,
            owner_id="test_owner",
            task_type="lyric_video_render",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        _lyric_video_render_job(db, job)

        render_updated = db.query(VideoRender).filter(VideoRender.id == render.id).first()
        job_updated = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()

        assert render_updated.status == "succeeded"
        assert render_updated.publish_status == "queued"
        assert job_updated.status == "succeeded"


class TestYouTubePublishJob:
    """Test YouTube publish job execution."""

    def test_youtube_publish_job_missing_render(self, db: Session):
        """Test job fails when render not found."""
        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id="nonexistent_render",
            status="running",
        )

        _youtube_publish_job(db, job)

        assert job.status == "failed"

    def test_youtube_publish_job_youtube_not_connected(self, db: Session):
        """Test job fails when YouTube not connected."""
        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
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

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        _youtube_publish_job(db, job)

        job_updated = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()
        assert job_updated.status == "failed"
        assert job_updated.error_code == "YT_NOT_CONNECTED"

    @patch("os.path.exists")
    @patch("backend.services.job_runner.publish_to_youtube")
    @patch("backend.services.job_runner.generate_metadata")
    @patch("backend.services.job_runner.decrypt_token")
    def test_youtube_publish_job_success(
        self, mock_decrypt, mock_metadata, mock_publish, mock_exists, db: Session
    ):
        """Test successful YouTube publish job."""
        mock_decrypt.return_value = "decrypted_token"
        mock_exists.return_value = True
        mock_metadata.return_value = MagicMock(
            title="Test Song",
            description="Test Description",
            tags=["music", "test"],
        )
        mock_publish.return_value = MagicMock(
            video_id="dQw4w9WgXcQ",
            url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            uploaded_at=datetime.now(timezone.utc),
        )

        song = StudioSong(
            id=new_id(),
            owner_id="test_owner",
            title="Test Song",
        )
        db.add(song)

        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=song.id,
            asset_id=new_id(),
            job_id=new_id(),
            render_format="music_visualizer",
            status="succeeded",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(render)

        conn = PlatformConnection(
            id=new_id(),
            owner_id="test_owner",
            provider="youtube",
            account_id="test_account",
            account_name="Test Account",
            access_token_encrypted="encrypted_token",
            granted_scopes_json=["youtube"],
            status="connected",
        )
        db.add(conn)

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        _youtube_publish_job(db, job)

        render_updated = db.query(VideoRender).filter(VideoRender.id == render.id).first()
        job_updated = db.query(AnalysisJob).filter(AnalysisJob.id == job.id).first()

        assert render_updated.status == "succeeded"
        assert render_updated.publish_status == "published"
        assert job_updated.status == "succeeded"
        assert "youtube" in render_updated.platform_urls

    @patch("os.path.exists")
    @patch("backend.services.job_runner.publish_to_youtube")
    @patch("backend.services.job_runner.generate_metadata")
    @patch("backend.services.job_runner.decrypt_token")
    def test_youtube_publish_job_passes_song_title(
        self, mock_decrypt, mock_metadata, mock_publish, mock_exists, db: Session
    ):
        """Test that actual song title is passed to generate_metadata, not UUID."""
        mock_decrypt.return_value = "decrypted_token"
        mock_exists.return_value = True
        mock_metadata.return_value = MagicMock(
            title="My Song Title",
            description="Test Description",
            tags=["music"],
        )
        mock_publish.return_value = MagicMock(
            video_id="test_id",
            url="https://youtube.com/watch?v=test_id",
            uploaded_at=datetime.now(timezone.utc),
        )

        song = StudioSong(
            id=new_id(),
            owner_id="test_owner",
            title="My Song Title",
        )
        db.add(song)

        render = VideoRender(
            id=new_id(),
            owner_id="test_owner",
            song_id=song.id,
            asset_id=new_id(),
            job_id=new_id(),
            render_format="music_visualizer",
            status="succeeded",
            render_settings_json={},
            scene_plan_json=[],
            provenance_json={},
        )
        db.add(render)

        conn = PlatformConnection(
            id=new_id(),
            owner_id="test_owner",
            provider="youtube",
            account_id="test_account",
            account_name="Test Artist",
            access_token_encrypted="encrypted_token",
            granted_scopes_json=["youtube"],
            status="connected",
        )
        db.add(conn)

        job = AnalysisJob(
            id=new_id(),
            owner_id="test_owner",
            task_type="youtube_publish",
            subject_id=render.id,
            status="running",
        )
        db.add(job)
        db.commit()

        _youtube_publish_job(db, job)

        # Verify that generate_metadata was called with the actual song title, not the UUID
        mock_metadata.assert_called_once()
        call_args = mock_metadata.call_args
        assert call_args[1]["song_title"] == "My Song Title"
        # Make sure it's not the UUID
        assert call_args[1]["song_title"] != song.id
