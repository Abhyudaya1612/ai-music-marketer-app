"""Tests for YouTube publisher service."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from googleapiclient.errors import HttpError

from backend.services.youtube_publisher import (
    publish_to_youtube,
    YouTubeVideo,
    YouTubePublishError,
)


class TestYouTubePublisher:
    """Test YouTube video publishing."""

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_publish_success(self, mock_creds_class, mock_build):
        """Test successful video upload."""
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        # Mock YouTube API
        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = {"id": "dQw4w9WgXcQ"}
        mock_request.execute.return_value = mock_response
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        result = publish_to_youtube(
            access_token="test_token",
            title="Test Video",
            description="Test Description",
            tags=["music", "test"],
            is_public=False,
        )

        assert isinstance(result, YouTubeVideo)
        assert result.video_id == "dQw4w9WgXcQ"
        assert "dQw4w9WgXcQ" in result.url
        assert isinstance(result.uploaded_at, datetime)

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_token_expired_no_refresh_token(self, mock_creds_class, mock_build):
        """Test error when token is expired and no refresh token available."""
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = None
        mock_creds_class.return_value = mock_creds

        with pytest.raises(YouTubePublishError) as exc_info:
            publish_to_youtube(
                access_token="expired_token",
                title="Test",
                description="Desc",
            )

        error = exc_info.value
        assert error.code == "YT_TOKEN_EXPIRED"
        assert "reconnect" in error.message.lower()
        assert error.is_recoverable is False

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_publish_unlisted_by_default(self, mock_creds_class, mock_build):
        """Verify video is unlisted by default."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = {"id": "test_id"}
        mock_request.execute.return_value = mock_response
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        publish_to_youtube(
            access_token="test_token",
            title="Test",
            description="Desc",
            is_public=False,
        )

        # Check that privacyStatus was set to "unlisted"
        call_args = mock_youtube.videos.return_value.insert.call_args
        body = call_args[1]["body"]
        assert body["status"]["privacyStatus"] == "unlisted"

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_publish_public_when_requested(self, mock_creds_class, mock_build):
        """Test public privacy setting."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = {"id": "test_id"}
        mock_request.execute.return_value = mock_response
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        publish_to_youtube(
            access_token="test_token",
            title="Test",
            description="Desc",
            is_public=True,
        )

        call_args = mock_youtube.videos.return_value.insert.call_args
        body = call_args[1]["body"]
        assert body["status"]["privacyStatus"] == "public"

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_quota_exceeded_error(self, mock_creds_class, mock_build):
        """Test quota exceeded (recoverable error)."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        # Create a mock HttpError with 403 status
        mock_response = MagicMock()
        mock_response.status = 403
        mock_request.execute.side_effect = HttpError(mock_response, b"Quota exceeded")
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        with pytest.raises(YouTubePublishError) as exc_info:
            publish_to_youtube(
                access_token="test_token",
                title="Test",
                description="Desc",
            )

        error = exc_info.value
        assert error.code == "YT_QUOTA_EXCEEDED"
        assert error.is_recoverable is True

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_auth_failed_error(self, mock_creds_class, mock_build):
        """Test authentication failure (permanent error)."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 401
        mock_request.execute.side_effect = HttpError(mock_response, b"Unauthorized")
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        with pytest.raises(YouTubePublishError) as exc_info:
            publish_to_youtube(
                access_token="test_token",
                title="Test",
                description="Desc",
            )

        error = exc_info.value
        assert error.code == "YT_AUTH_FAILED"
        assert error.is_recoverable is False

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_invalid_video_error(self, mock_creds_class, mock_build):
        """Test invalid video file (permanent error)."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 400
        mock_request.execute.side_effect = HttpError(mock_response, b"Bad request")
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        with pytest.raises(YouTubePublishError) as exc_info:
            publish_to_youtube(
                access_token="test_token",
                title="Test",
                description="Desc",
            )

        error = exc_info.value
        assert error.code == "YT_INVALID_VIDEO"
        assert error.is_recoverable is False

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_server_error_recoverable(self, mock_creds_class, mock_build):
        """Test server error (recoverable)."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 500
        mock_request.execute.side_effect = HttpError(mock_response, b"Server error")
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        with pytest.raises(YouTubePublishError) as exc_info:
            publish_to_youtube(
                access_token="test_token",
                title="Test",
                description="Desc",
            )

        error = exc_info.value
        assert "YT_" in error.code
        assert error.is_recoverable is True

    @patch("backend.services.youtube_publisher.build")
    @patch("backend.services.youtube_publisher.Credentials")
    def test_metadata_truncation(self, mock_creds_class, mock_build):
        """Test that metadata is properly truncated to limits."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds_class.return_value = mock_creds

        mock_youtube = MagicMock()
        mock_request = MagicMock()
        mock_response = {"id": "test_id"}
        mock_request.execute.return_value = mock_response
        mock_youtube.videos.return_value.insert.return_value = mock_request
        mock_build.return_value = mock_youtube

        long_title = "A" * 150
        long_description = "B" * 6000

        publish_to_youtube(
            access_token="test_token",
            title=long_title,
            description=long_description,
        )

        call_args = mock_youtube.videos.return_value.insert.call_args
        body = call_args[1]["body"]
        assert len(body["snippet"]["title"]) <= 100
        assert len(body["snippet"]["description"]) <= 5000
