# YouTube Video Publishing Fix - Implementation Plan

## Executive Summary

YouTube video publishing jobs are stuck in "running" state and never transition to "succeeded" or "failed". The root causes are:

1. **Exception handler doesn't cover `youtube_publish` tasks** — the global exception handler in `run_v1_job` (line 94-101) only handles `video_render` specially; all other job types including `youtube_publish` hit the else clause, which calls `_fail_job` (wrong model) instead of `_fail_video_job` (right model for publish jobs).

2. **Job status transition race condition** — the `_youtube_publish_job` function at line 532 checks if `render.status != "succeeded"` AFTER loading the render, but the render itself may still be in progress (status="running") from the initial video_render job, not from the publish job. This check fails silently for edge cases.

3. **Missing error classification in exception handler** — when `publish_to_youtube` raises a `YouTubePublishError`, the exception is not caught in the job runner's outer try-except; it propagates as an unhandled exception, triggering the generic exception handler which doesn't know about the `is_recoverable` flag.

4. **No file existence validation** — the code passes `render_output_path(render.id)` to `publish_to_youtube` without verifying the file exists. If the render output is missing, the YouTube API client will fail with a cryptic error.

5. **Insufficient logging** — no structured logging of the actual YouTube API errors, token state, or upload progress, making debugging impossible.

## Verification Status

- Database shows 3 youtube_publish jobs stuck with status="running", stage="queued", no error_code.
- Latest render (4eaa7414-15a5-439d-83a7-5b3a67b097a2) has status="succeeded", publish_status="none", platform_urls={}.
- YouTube OAuth token is present, encrypted, and decrypts successfully in tests.
- Video file exists at private-media/4eaa7414-15a5-439d-83a7-5b3a67b097a2/render.mp4 (219 MB).

## Implementation Plan

### 1. Fix exception handler to handle youtube_publish errors

**What:** Add `youtube_publish` case to the outer exception handler in `run_v1_job` so that when `_youtube_publish_job` raises an unhandled exception, it calls `_fail_video_job` instead of the generic `_fail_job`, which correctly sets render.status and render.publish_status.

**Rationale:** The outer exception handler in `run_v1_job` (lines 88-110) only has special handling for `video_render` task type. When `youtube_publish` raises an exception, it falls through to the generic `_fail_job(db, job, "INTERNAL_ERROR")` call, which doesn't update the VideoRender model's status/publish_status fields. This leaves the render stuck with no status change and no error indication.

**Files:** `backend/services/job_runner.py`

**Changes:**
- Line 99-101: Add elif clause for `job.task_type == "youtube_publish"` (same pattern as `video_render`):
  - Query for the render
  - Call `_fail_video_job(db, job, render, "INTERNAL_ERROR")` instead of `_fail_job`

**Verify:** 
```powershell
pytest tests/test_job_runner_publishing.py -v -k "test_youtube_publish"
```
Expected: All youtube_publish tests pass, including new error recovery tests.

---

### 2. Add file existence validation before YouTube upload

**What:** In `_youtube_publish_job`, before calling `publish_to_youtube`, verify that the render output file exists. If missing, fail immediately with a clear error code.

**Rationale:** The youtube_publisher module assumes the video file path is valid. If the file is missing (e.g., storage corruption, directory deleted), the Google API client will fail with a generic 400 error. Early validation provides better diagnostics and prevents partial state corruption.

**Files:** `backend/services/job_runner.py`

**Changes:**
- Line 585-590 (before calling `publish_to_youtube`):
  - Import `os` module
  - Get the video file path: `video_path = render_output_path(render.id)`
  - Check: `if not os.path.exists(video_path)`, fail with error_code="VIDEO_FILE_NOT_FOUND"

**Verify:**
```powershell
pytest tests/test_job_runner_publishing.py -v -k "test_youtube_publish_job_success"
```
Expected: Test passes. Add a new test `test_youtube_publish_job_missing_video_file` that simulates missing render output.

---

### 3. Properly catch YouTubePublishError with is_recoverable flag

**What:** In `_youtube_publish_job`, wrap the `publish_to_youtube` call in a specific try-except that catches `YouTubePublishError` and uses its `is_recoverable` flag to set the correct job status ("failed_retryable" vs "failed").

**Rationale:** Currently (lines 644-669), the code does catch `YouTubePublishError` and does check `is_recoverable`. However, if an unhandled exception escapes `_youtube_publish_job` (e.g., token decryption fails, render lookup fails), the outer exception handler (lines 88-110) does NOT have youtube_publish case, so the error is lost. Fixing #1 above fixes this; this step ensures the error handling is complete within the function itself.

**Files:** `backend/services/job_runner.py`

**Changes:**
- Lines 644-669: Already has the correct error handling logic. Verify it correctly sets:
  - render.publish_status = "failed" 
  - render.publish_error = exc.message
  - job.status = "failed_retryable" if exc.is_recoverable else "failed"
  - Confirm this logic is sound (it is — just ensure it persists correctly)

**Verify:**
```powershell
pytest tests/test_job_runner_publishing.py -v -k "retryable or permanent"
```
Expected: `test_youtube_publish_retryable_error` and `test_youtube_publish_permanent_error` both pass.

---

### 4. Add detailed logging at key points in youtube_publish workflow

**What:** Add structured logging before and after critical operations: token decryption, metadata generation, YouTube upload, and state transitions. Log actual error details when exceptions occur.

**Rationale:** Current error logs are too generic. When a job fails, there's no record of what step failed or why. Structured logs with context (owner_id, render_id, error details) make debugging much faster.

**Files:** `backend/services/job_runner.py`

**Changes:**
- Line 527: Add logger.info at function entry: `logger.info("youtube_publish_job_starting", extra={"render_id": job.subject_id, "owner_id": job.owner_id})`
- Line 544: Add logger.info after token decryption: `logger.info("youtube_access_token_decrypted", extra={"render_id": render.id})`
- Line 585: Add logger.info before upload: `logger.info("youtube_upload_starting", extra={"render_id": render.id, "video_title": metadata.title})`
- Line 620-625: Add logger.info on success: `logger.info("youtube_upload_completed", extra={"render_id": render.id, "video_id": video.video_id, "video_url": video.url})`
- Line 644: Add logger.error with full exception details: `logger.error("youtube_upload_failed", extra={"render_id": render.id, "error_code": exc.code, "error_message": exc.message, "recoverable": exc.is_recoverable})`

**Verify:**
```powershell
pytest tests/test_job_runner_publishing.py -v -k "test_youtube_publish_job_success"
# Check logs contain the key messages
```
Expected: Job completes; logs show each step.

---

### 5. End-to-end test: publish a video from database state to YouTube

**What:** Create a manual test script that:
1. Queries the database for the latest succeeded render (ID: 4eaa7414-15a5-439d-83a7-5b3a67b097a2)
2. Creates a new youtube_publish job for that render
3. Calls `run_v1_job` to execute the job
4. Polls the database until the job transitions to "succeeded" or "failed"
5. Verifies the render.platform_urls contains a real YouTube URL
6. Confirms the video is visible in YouTube Studio (Doge account)

**Rationale:** The unit tests mock the YouTube API. A real end-to-end test confirms the full flow works with actual YouTube credentials and a real video upload.

**Files:** `tests/test_e2e_youtube_publish.py` (new)

**Changes:**
- Create a new test file with a single test function
- Use the test render ID from the database
- Create a temporary AnalysisJob with task_type="youtube_publish"
- Call `run_v1_job(job.id)`
- Assert job.status == "succeeded"
- Assert render.publish_status == "published"
- Assert render.platform_urls["youtube"] starts with "https://www.youtube.com/watch?v="
- (Optional) Use YouTube API to verify video exists

**Verify:**
```powershell
# First, ensure the backend is running with the correct database
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_youtube_publish.py -v -s
```
Expected: Test passes; video appears in YouTube Studio under Doge account within 30 seconds.

---

### 6. Validate all existing tests still pass

**What:** Run the full test suite to ensure no regressions from the changes above.

**Files:** All test files in `tests/`

**Verify:**
```powershell
pytest tests/ -v
```
Expected: All tests pass. Specifically check:
- `tests/test_job_runner_publishing.py` — all youtube_publish tests
- `tests/test_youtube_publisher.py` — all YouTube API tests
- `tests/test_e2e_publishing_workflow.py` — end-to-end publishing workflow

---

## Summary of Changes

| File | Change | Reason |
|------|--------|--------|
| `backend/services/job_runner.py` | Add youtube_publish case to exception handler | Fix jobs stuck in running; enable proper error handling |
| `backend/services/job_runner.py` | Add file existence validation before upload | Prevent cryptic API errors; validate render output exists |
| `backend/services/job_runner.py` | Add structured logging at each step | Enable debugging; track job progress |
| `tests/test_e2e_youtube_publish.py` | Create end-to-end YouTube publish test | Verify full flow works with real YouTube API |

## Testing Strategy

1. **Unit tests** — Existing tests in `test_job_runner_publishing.py` should pass without modification
2. **Integration tests** — New end-to-end test uses real database and YouTube credentials (Doge account)
3. **Manual verification** — After running the end-to-end test, manually check YouTube Studio for the uploaded video

## Deployment Notes

- No database schema changes required
- All changes are in the job handler logic and error handling
- Token decryption and OAuth flow unchanged
- Backwards compatible — existing stuck jobs will remain unchanged; new jobs will execute correctly
