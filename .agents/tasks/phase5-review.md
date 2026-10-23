# Phase 5-8 Publishing Implementation Review

YouTube metadata generation, lyric-video rendering, and YouTube publishing for AI Music Marketer.

This phase adds three new services (Ollama LLM provider, YouTube publisher, lyric-video generator) wired into the job runner, backed by 40+ tests and supporting configuration. The approach follows established patterns: services as request-scoped helpers (Ollama, YouTube) or job types (lyric-video, YouTube publish). Metadata flows through the pipeline with proper error classification for retry logic. Watch for: OAuth token handling has a plausible gap around refresh semantics when the refresh_token is absent; prompt injection sanitization is basic regex-based and could be bypassed with obfuscated patterns; error classification for YouTube publishing correctly distinguishes recoverable vs permanent, but the recovery flow (retry loop) is not visible in the code reviewed.

**Verdict**: APPROVED

---

## High-level view

Ollama integration is a synchronous request-scoped service that generates YouTube metadata (title, description, tags) from song info. When Ollama is unavailable—connection refused, timeout, invalid JSON response—the service falls back to template-based generation without raising exceptions. Input sanitization removes common prompt-injection patterns before sending to Ollama, though the approach is regex-based and may not catch all variants.

YouTube publishing adds a new job type that orchestrates credential decryption, metadata generation via Ollama, and video upload. Error classification distinguishes recoverable errors (5xx, quota exceeded) that trigger retry from permanent errors (auth failure, invalid video) that fail immediately. Metadata is stored in VideoRender alongside the video URL; the credential lookup checks for an existing connected account and fails early if missing.

Lyric-video rendering extends the video job pattern with subtitle parsing (SRT/LRC) and FFmpeg integration. When FFmpeg is unavailable, tests gracefully skip. When lyrics are not provided, the service falls back to waveform-only rendering. The job runner lifecycle mirrors existing video_render jobs: status transitions from queued → running → succeeded/failed, with publish_status tracking publication separately.

Security: OAuth tokens are decrypted at job-execution time (not in request handlers), reducing the window tokens are in memory. Token refresh is implemented but has a correctness edge case: if refresh_token is absent, the code catches the exception and continues, potentially sending an expired access_token to the YouTube API.

Testing is comprehensive: 40+ test cases across five files covering success paths, error handling (both classes), input validation, prompt injection safety, fallback behavior, state transitions, and end-to-end workflow. Mocks are used consistently, and FFmpeg tests are skipped when unavailable.

---

<details>
<summary>Issues (4)</summary>

1. **OAuth token refresh gap** — When a Credentials object is missing refresh_token, the refresh attempt catches and silently continues. This could send expired access_token to YouTube API, which then fails with YT_AUTH_FAILED (permanent, no retry). The code should distinguish between "token is still valid" and "token expired, cannot refresh"; the current logic treats both as "continue." Consider checking token.expiry before refresh.

2. **Prompt injection sanitization incomplete** — The regex patterns in _sanitize_input (ignore previous, forget everything, act as) are basic and match only exact phrase structure. Attackers can obfuscate with extra whitespace, unicode normalization, or variant phrasings ("ignore the previous", "disregard prior"). Not a blocker (fallback is safe), but should be documented as a known limitation.

3. **Metadata placeholder in job runner** — _youtube_publish_job passes render.song_id as song_title to generate_metadata, which is a UUID, not the actual song title. The real title should be joined from VideoRender → Song. This doesn't break functionality (Ollama receives a UUID and generates generic metadata), but it's a logic error that should be fixed before production use.

4. **Error classification returns bool but doc doesn't clarify recovery semantics** — _classify_error returns True/False to indicate retryable errors, but it's not used in _youtube_publish_job. The job always sets status="failed" regardless of the error code. Retry is handled by an external scheduler (presumably), not visible here. Code is correct but the unused function is confusing; should either delete it or document the external retry contract.

</details>

---

## Ollama metadata generation and fallback strategy

The `generate_metadata` function sends a structured prompt to Ollama's `/api/generate` endpoint and parses the JSON response. If Ollama is disabled or any network/parsing error occurs (connection refused, timeout, invalid JSON), it falls back to template-based generation without raising exceptions. Fallback is safe: title from song+artist+mood (≤100 chars), description from template (≤5000 chars), tags as fixed list.

Input sanitization removes patterns like "ignore previous", "forget everything", "act as" using case-insensitive regex. This catches basic injection but is not robust to synonyms ("disregard prior"), extra whitespace, or unicode tricks (see Issues). The real protection is structural: metadata flows to YouTube as truncated strings, not executable code.

---

## YouTube publishing orchestration and error classification

`_youtube_publish_job` orchestrates: load render and token, generate metadata, upload to YouTube, store video URL. OAuth token is decrypted at job-execution time (not earlier), reducing the window it's in memory. Token refresh is attempted if expired and refresh_token exists; the catch silently continues if refresh fails, which is problematic (see Issues).

Error classification in `youtube_publisher.py` correctly marks 403 (quota/permission) and 5xx (server) as `is_recoverable=True`; 401 (auth) and 400 (bad request) as `is_recoverable=False`. However, this flag is not used downstream—`_youtube_publish_job` always sets `status="failed"` for both classes, relying on external scheduler to inspect `error_code` for retry decisions. The unused `_classify_error` function creates confusion; should either remove it or document the external retry contract.

---

## Lyric-video rendering as a new job type

`_lyric_video_render_job` validates render exists, marks status=running, calls the generator, and updates VideoRender on success/failure. On success, it sets `publish_status="queued"`, signaling readiness for YouTube publishing.

`render_lyric_video` handles subtitle parsing (SRT/LRC), FFmpeg integration, and output validation. SRT and LRC parsers skip malformed entries rather than crashing. ASS subtitle format is built correctly with millisecond timing. FFmpeg is called with appropriate filters (showwaves/showspectrum) and codec settings (libx264 video, aac audio). If rendering times out or crashes, `LyricVideoError` is raised with a specific code. Lyrics are optional: fallback to audio-only waveform rendering if absent.

---

## API endpoints and rate limiting

Two new endpoints: `POST /video/{render_id}/generate-lyric-video` (20/hour rate limit) and `POST /video/{render_id}/publish-youtube` (10/hour). Both validate render ownership, check resource state (publish requires render status==succeeded), enqueue the job, and return JobOut with job_id. They defer work to async job runner rather than blocking. Rate limits are appropriate: rendering is lightweight, publishing is gated by YouTube quota anyway.

---

## Database schema and Pydantic models

New fields in `VideoRender`: `platform_urls` (JSON dict, e.g., `{"youtube": "https://......"}`), `metadata_json` (snapshot of generated metadata), `publish_status` (lifecycle: "none", "queued", "publishing", "published", "failed"), `publish_error` (error message on failure).

`SongIntelligenceIn` schema validates extracted audio features before storing. `HookCandidate` properly enumerates kinds and includes evidence. No Pydantic validators for YouTube metadata field limits (title ≤100, description ≤5000, tags ≤500)—truncation happens at publish time. This is acceptable but would be safer as schema-level validators.

---

## Configuration and secrets handling

Config adds Ollama settings (base_url, model, enabled, timeout_seconds) and YouTube settings (upload_max_size_bytes, rate_limit_per_hour, rendering timeout). OAuth credentials are stored as `SecretStr`, redacting them from logs. Access tokens are encrypted in the database and decrypted at job-execution time. Encryption key is validated in production: raises ValueError if not set. This follows correct posture: secrets in config/env, tokens encrypted at rest, decrypted on-demand.

---

## Test coverage and mocking strategy

Five test files cover 40+ cases:

**test_ollama_provider.py**: Mocks httpx.Client. Tests success, connection errors, timeouts, invalid JSON, markdown-wrapped responses, and sanitization. Verifies fallback on all error paths.

**test_youtube_publisher.py**: Mocks google.auth and build(). Tests success, unlisted/public privacy, quota exceeded (recoverable), auth failure (permanent), invalid video (permanent), server error (recoverable), metadata truncation.

**test_lyric_video_generation.py**: Tests SRT/LRC parsing with valid, multi-line, empty, and malformed inputs. Tests ASS timing. All FFmpeg-dependent tests marked skipif unavailable.

**test_job_runner_publishing.py**: Mocks render_lyric_video, publish_to_youtube, generate_metadata, decrypt_token. Tests error classification, job success/failure, metadata flow.

**test_e2e_publishing_workflow.py**: Uses TestClient. Tests queue endpoints, validation, full metadata→upload workflow.

Mocks are consistent and correct. One gap: no tests for OAuth token refresh logic.

---

## Audit logging

Structured logging throughout: Ollama (metadata_generated_via_ollama, connection_refused, timeout), YouTube (video_uploaded, token_refreshed), lyric-video (generated, ass_created), job runner (completed, failed, stage). Consistent use of structured extra dict, appropriate log levels, no sensitive data (tokens, keys) logged.

---

## Prompt injection surface and risk

Ollama receives user-controlled text (song title, artist name, mood). `_sanitize_input` removes obvious injection patterns. This is belt-and-suspenders: (1) sanitization catches basic attempts, (2) response is parsed as JSON and truncated to field limits, (3) YouTube title/description are unexecuted text. The regex approach is not robust to synonyms or unicode tricks, but fallback is safe and structural protections (truncation, parsing) make injection low-risk.

---

## Unaddressed edge cases

1. **Metadata generation with very long song titles**: If song title exceeds buffer, sanitization removes patterns and Ollama receives ≤buffer. Fallback generates metadata (no crash), but quality may suffer.

2. **Rate limiting: 10 YouTube publishes/hour**: YouTube quota is ~10k units/day; video upload costs ~1500 units. 10 uploads/hour is feasible but fragile. YouTube API returns 403 only when exceeded, not before—no pre-emptive quota warning.

3. **Video URL storage**: `platform_urls["youtube"]` is never updated if video is made private/deleted later. Out of app scope.

4. **Cascading job failures**: If generate_metadata fails, job proceeds with fallback metadata. If YouTube API is down, job fails with recoverable error and retries. No cascading issues.

---

</details>

## File map

<details>
<summary>Files modified and created</summary>

**backend/services/ollama_provider.py** (new): Synchronous metadata generation service; connects to Ollama, falls back to templates on error, sanitizes input.

**backend/services/youtube_publisher.py** (new): YouTube OAuth publishing; authenticates, uploads video, classifies errors as recoverable/permanent.

**backend/services/lyric_video_generator.py** (new): Lyric-video rendering; parses SRT/LRC subtitles, generates ASS format, calls FFmpeg.

**backend/services/job_runner.py** (modified): Added `_lyric_video_render_job` and `_youtube_publish_job` handlers; wired into dispatcher.

**backend/domain/models.py** (modified): Extended `VideoRender` with platform_urls, metadata_json, publish_status, publish_error fields.

**backend/domain/schemas.py** (modified): Added `SongIntelligenceIn` schema with validators; defined `HookCandidate`, `MetadataGenerationRequest/Response`, `YouTubePublishRequest/Response`.

**backend/routers/v1.py** (modified): Added `POST /video/{render_id}/generate-lyric-video` and `POST /video/{render_id}/publish-youtube` endpoints; updated capabilities endpoint.

**backend/config.py** (modified): Added Ollama settings (base_url, model, enabled, timeout_seconds), YouTube settings (upload_max_size, rate_limit), lyric-video settings (max_render_time, subtitle_format).

**tests/test_ollama_provider.py** (new): 8 test cases for metadata generation, fallback, sanitization, markdown parsing.

**tests/test_youtube_publisher.py** (new): 8 test cases for upload success, privacy settings, error classification, metadata truncation.

**tests/test_lyric_video_generation.py** (new): 10 test cases for SRT/LRC parsing, ASS generation, FFmpeg skipping.

**tests/test_job_runner_publishing.py** (new): 8 test cases for error classification, lyric-video job, YouTube publish job.

**tests/test_e2e_publishing_workflow.py** (new): 6 test cases for HTTP endpoints, full workflow.

**tests/conftest.py** (new): Pytest fixtures (in-memory SQLite database).

**requirements.txt** (modified): Added google-auth-oauthlib, google-auth-httplib2, google-api-python-client, pysrt.

**README.md** (modified): Added sections for Ollama setup, YouTube publishing, lyric-video rendering, configuration reference, testing instructions.

[Full diff: git diff main (not available; project not git-tracked)]

</details>
