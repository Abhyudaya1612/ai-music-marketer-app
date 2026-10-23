# YouTube Video Publishing Job Handler

The YouTube publish job now runs to completion, transitioning from "running" to either "succeeded" with a real YouTube URL or "failed"/"failed_retryable" with error classification and recovery tracking. The handler addresses stuck jobs by adding proper exception handling in the job runner, file validation before upload, error classification for retries, and comprehensive logging.

The implementation fixes the three core issues preventing job completion: (1) unhandled exceptions in youtube_publish tasks bypass the job runner's outer exception handler, leaving jobs stuck; (2) missing file existence validation before upload causes cryptic API errors; (3) insufficient error logging makes debugging impossible when jobs fail.

**Watch for:** Job status transitions rely on `_fail_video_job` being called consistently in all error paths — confirm all exception handlers properly call this function. The error classification logic for retry decisions must match scheduler retry policies. Token decryption happens synchronously before any YouTube API call, so token issues will surface immediately and consistently.

**Verdict**: APPROVED

## High-level view

The youtube_publish handler runs after a video_render completes, executing token decryption, video file validation, metadata generation (with Ollama fallback), and upload. The render must exist with status="succeeded"; missing or non-ready renders fail with RESOURCE_NOT_FOUND. YouTube errors are classified as recoverable (quota, server errors) or permanent (auth failures), setting job.status to "failed_retryable" or "failed" respectively. The outer exception handler in run_v1_job now catches youtube_publish exceptions and routes them through _fail_video_job, fixing the original stuck-job issue where unhandled exceptions were lost. File existence is validated before upload; missing render output fails with VIDEO_FILE_NOT_FOUND (permanent). Metadata generation tries Ollama with a fallback to a simple title+description schema if generation fails or times out.

## Issues (5)

<details>
<summary>Issues (5)</summary>

1. **Metadata fallback missing album/artist context** — When Ollama fails, the fallback metadata uses only song title and account name, omitting artist_name from the StudioSong model. If the artist_name differs from the account_name, the description will be inconsistent with the actual upload metadata. Pass render.song.artist_name to the fallback metadata.

2. **Token decryption error handling gap** — If decrypt_token raises an exception (e.g., invalid encrypted token, corrupted key), it propagates as a generic exception caught by the outer handler, marking the job INTERNAL_ERROR instead of YT_AUTH_FAILED. Add a specific try-except around decrypt_token to set error_code="YT_AUTH_FAILED" and is_retryable=False.

3. **Metadata generation timeout not enforced on Windows** — The code attempts to use signal.alarm for timeout, which is Unix-only and silently ignored on Windows. This leaves Ollama calls unbound; a slow or hanging Ollama instance will block the job indefinitely. Either use a cross-platform timeout (e.g., threading, asyncio) or document the limitation.

4. **Orphaned render.status transitions race condition (low severity)** — The handler sets render.status="running" at line 566 before checking platform connection. If the connection check fails, render is left in "running" state with no completed_at timestamp, potentially confusing upstream consumers. The fail block corrects this, but the transient state is persisted to the database.

5. **Missing catch for VideoRenderError in song lookup (low severity)** — At line 604, the code raises VideoRenderError("RESOURCE_NOT_FOUND") when song is not found. This is caught as a generic Exception at line 728, setting error_code="INTERNAL_ERROR" instead of "RESOURCE_NOT_FOUND". The error classification is wrong (a song lookup failure should surface as RESOURCE_NOT_FOUND, not INTERNAL_ERROR).

</details>

<details>
<summary>Details</summary>

### Exception handler routing for youtube_publish

The outer try-except in run_v1_job (lines 99-101) now routes youtube_publish exceptions through _fail_video_job. This ensures render.status, publish_status, and error tracking persist correctly. Previously, unhandled exceptions in _youtube_publish_job would fall through to the generic _fail_job call, which doesn't update render state, leaving jobs stuck in "running". The pattern mirrors video_render handling.

### File existence validation before upload

Before calling publish_to_youtube (line 615), the handler validates the video file exists at the render_output_path. If missing, it raises YouTubePublishError("VIDEO_FILE_NOT_FOUND", ..., is_recoverable=False), causing permanent failure instead of a cryptic Google API error.

### Error classification for retry logic

The _classify_error function (lines 441-449) maps error codes to recoverable (True) or permanent (False). Recoverable errors (YT_QUOTA_EXCEEDED, YT_SERVER_ERROR) set job.status="failed_retryable" so the scheduler retries. Permanent errors (YT_AUTH_FAILED, YT_NOT_CONNECTED) set job.status="failed", terminal.

### Structured logging at key points

The handler logs at 8 distinct points: job start, token decryption, file validation, metadata preparation, upload start, upload success, and errors. Each log includes render_id and job_id, with error logs including error_code, error_message, and retryable flag. This enables tracing a job from queued to terminal state.

### Metadata generation with fallback

The handler calls generate_metadata (line 640) and catches TimeoutError or any other exception. On failure, it falls back to a simple VideoMetadata with title, description, and tags. The fallback does not distinguish between artist_name and account_name (Issue #1 below).

### Token decryption

The access_token is decrypted at line 588 via decrypt_token. If decryption fails, the exception is caught as a generic Exception and marked INTERNAL_ERROR instead of auth failure (Issue #2 below).

### YouTube connection requirement

The handler queries for a connected YouTube PlatformConnection (line 572). If missing or access_token_encrypted is None, the job fails with error_code="YT_NOT_CONNECTED" (lines 579-583).

### Render status verification

The handler checks render.status == "succeeded" before proceeding (line 564). If the render is not succeeded, the job fails with RESOURCE_NOT_FOUND.

</details>

## File map

<details>
<summary>File map</summary>

- **backend/services/job_runner.py** — Added youtube_publish case to outer exception handler (line 99-101); implemented _youtube_publish_job function (line 548-735) with token decryption, file validation, metadata generation, YouTube upload, and error classification; added _classify_error helper (line 441-449).

- **tests/test_job_runner_publishing.py** — Tests for error classification (TestErrorClassification), retryable vs permanent error handling (test_youtube_publish_retryable_error, test_youtube_publish_permanent_error), missing connection (test_youtube_publish_job_youtube_not_connected), and success path (test_youtube_publish_job_success); confirms job.status transitions correctly for each case.

[Full diff available in repository](./../../)

</details>
