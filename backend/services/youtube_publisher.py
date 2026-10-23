"""YouTube video publishing service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    url: str
    uploaded_at: datetime


class YouTubePublishError(Exception):
    def __init__(self, code: str, message: str, is_recoverable: bool = False):
        self.code = code
        self.message = message
        self.is_recoverable = is_recoverable
        super().__init__(f"{code}: {message}")


def publish_to_youtube(
    access_token: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    is_public: bool = False,
    video_file_path: str | None = None,
    refresh_token: str | None = None,
) -> YouTubeVideo:
    """
    Publish a video to YouTube.
    
    Args:
        access_token: OAuth2 access token for YouTube account
        title: Video title (max 100 chars)
        description: Video description (max 5000 chars)
        tags: List of tags (each max 500 chars)
        is_public: If False, video is unlisted (can be shared); if True, public
        video_file_path: Path to video file (for upload; optional in test)
        refresh_token: Optional refresh token for token refreshing
    
    Returns:
        YouTubeVideo with video_id and url
        
    Raises:
        YouTubePublishError with is_recoverable flag for retry logic
    
    Note:
        If the access token has expired and there is no refresh token available,
        a YT_TOKEN_EXPIRED error is raised (permanent failure). The caller should
        prompt the user to reconnect their YouTube account.
    """
    if tags is None:
        tags = []

    # Check for mock mode
    if settings.youtube_publish_mock_mode:
        import uuid
        mock_video_id = str(uuid.uuid4())[:11]  # Realistic-looking YouTube video ID format
        mock_url = f"https://www.youtube.com/watch?v={mock_video_id}"
        logger.info(
            "youtube_upload_mocked",
            extra={
                "title": title,
                "mock_video_id": mock_video_id,
                "mock_url": mock_url,
            },
        )
        return YouTubeVideo(video_id=mock_video_id, url=mock_url, uploaded_at=datetime.now(timezone.utc))

    # Build credentials object with refresh token if available
    credentials = Credentials(token=access_token, refresh_token=refresh_token)

    # Refresh if needed, but guard against expired token with no refresh capability
    try:
        if credentials.expired and credentials.refresh_token is None:
            raise YouTubePublishError(
                "YT_TOKEN_EXPIRED",
                "YouTube token expired and cannot be refreshed. Reconnect YouTube account.",
                is_recoverable=False,
            )
        if credentials.expired and credentials.refresh_token:
            request = Request()
            credentials.refresh(request)
            logger.info("youtube_token_refreshed")
    except YouTubePublishError:
        raise
    except Exception as e:
        raise YouTubePublishError(
            "YT_TOKEN_REFRESH_FAILED",
            f"Failed to refresh YouTube token: {e}",
            is_recoverable=False,
        )

    # Build YouTube API client
    try:
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    except Exception as e:
        raise YouTubePublishError(
            "YT_API_BUILD_FAILED",
            f"Failed to build YouTube API client: {e}",
            is_recoverable=False,
        )

    # Prepare request body
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [t[:500] for t in tags[:500]],  # YouTube allows up to 500 tags
            "categoryId": "10",  # Music category
        },
        "status": {
            "privacyStatus": "public" if is_public else "unlisted",
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        # Create the video metadata
        if video_file_path:
            logger.info("youtube_upload_with_file_starting", extra={"video_file_path": video_file_path})
            # Upload with file - use threading with timeout to prevent hanging
            from googleapiclient.http import MediaFileUpload
            import os
            import threading

            # Check file size
            file_size = os.path.getsize(video_file_path)
            if file_size > settings.youtube_upload_max_size_bytes:
                raise YouTubePublishError(
                    "YT_FILE_TOO_LARGE",
                    f"Video file {file_size} bytes exceeds limit {settings.youtube_upload_max_size_bytes}",
                    is_recoverable=False,
                )

            media = MediaFileUpload(video_file_path, mimetype="video/mp4", resumable=True)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            
            # Execute with timeout using threading
            result = [None]
            exception = [None]
            
            def execute_upload():
                try:
                    result[0] = request.execute()
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=execute_upload, daemon=False)
            thread.start()
            thread.join(timeout=600)  # 10-minute timeout for upload (allows for large files)
            
            if thread.is_alive():
                raise YouTubePublishError(
                    "YT_UPLOAD_TIMEOUT",
                    "YouTube upload timed out after 600 seconds",
                    is_recoverable=True,
                )
            
            if exception[0]:
                raise exception[0]
            
            response = result[0]
            if not response:
                raise YouTubePublishError(
                    "YT_UPLOAD_NO_RESPONSE",
                    "YouTube API returned no response",
                    is_recoverable=True,
                )
        else:
            logger.warning("youtube_upload_metadata_only", extra={"video_file_path": video_file_path})
            # Create metadata-only (for testing or existing videos)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
            )
            response = request.execute()

        logger.info(
            "youtube_api_response",
            extra={
                "response_keys": list(response.keys()) if response else "None",
                "full_response": str(response)[:500] if response else "None",
            },
        )
        
        video_id = response["id"]
        url = f"https://www.youtube.com/watch?v={video_id}"
        now = datetime.now(timezone.utc)

        logger.info(
            "youtube_video_uploaded",
            extra={
                "video_id": video_id,
                "url": url,
            },
        )

        return YouTubeVideo(video_id=video_id, url=url, uploaded_at=now)

    except HttpError as e:
        error_code = e.resp.status
        if error_code == 403:
            # Quota exceeded or permission denied
            raise YouTubePublishError(
                "YT_QUOTA_EXCEEDED",
                "YouTube API quota exceeded or permission denied",
                is_recoverable=True,  # Recoverable: retry later
            )
        elif error_code == 401:
            # Unauthorized: token invalid or revoked
            raise YouTubePublishError(
                "YT_AUTH_FAILED",
                "YouTube authentication failed (token invalid or revoked)",
                is_recoverable=False,
            )
        elif error_code == 400:
            # Bad request: invalid video or metadata
            raise YouTubePublishError(
                "YT_INVALID_VIDEO",
                f"Invalid video or metadata: {e}",
                is_recoverable=False,
            )
        elif 500 <= error_code < 600:
            # Server error: recoverable
            raise YouTubePublishError(
                "YT_SERVER_ERROR",
                f"YouTube server error: {error_code}",
                is_recoverable=True,
            )
        else:
            # Other HTTP error
            raise YouTubePublishError(
                f"YT_HTTP_{error_code}",
                f"YouTube HTTP error: {error_code}",
                is_recoverable=(error_code >= 500),
            )
    except Exception as e:
        raise YouTubePublishError(
            "YT_UPLOAD_FAILED",
            f"Unexpected error uploading to YouTube: {type(e).__name__}: {e}",
            is_recoverable=True,  # Assume recoverable for network/transient issues
        )
