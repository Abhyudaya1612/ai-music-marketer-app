# Phases 5–8 Implementation Plan: Ollama LLM, YouTube Publishing, Lyric-Video Generation

## Planning Basis

This plan implements all 12 deliverables for Phases 5–8 of the AI Music Marketer. The exploration confirmed:

- **Project structure**: Single-workspace FastAPI backend, SQLite database with v1_* tables, background job runner with job types (`asset_verification`, `song_analysis`, `video_render`).
- **Test patterns**: pytest with monkeypatch, real test client against FastAPI app, skip guards for optional dependencies (FFmpeg, librosa, essentia).
- **Config pattern**: Pydantic `BaseSettings` with `env_prefix="APP_"`, `SecretStr` for sensitive values, startup validation.
- **Job runner pattern**: Jobs transition through states (queued → running → succeeded/failed), stored in `v1_jobs` with `task_type`, `subject_id`, and retry logic (max 3 attempts).
- **Database schema**: SQLAlchemy ORM with Column types (String, JSON, DateTime, Boolean), relationships via ForeignKey, auto UTC timestamps with `utcnow()` and `onupdate=utcnow`.
- **API patterns**: Bearer token auth, owner-scoped queries, rate limiting via slowapi decorators, 5 status codes, SafeError responses, Pydantic request/response schemas.
- **Secrets**: YouTube OAuth credentials already configured in `backend/config.py` (client_id, client_secret, redirect_uri).
- **Video rendering**: FFmpeg integration in `backend/services/video_rendering.py` for motion graphics, returns MP4 output.

## Architecture Decisions

### 1. Ollama LLM Adapter (Deliverable 1)
**Decision**: Create new `backend/services/ollama_provider.py` as a synchronous service module (not a job type) that can be called from within `youtube_publish` job and from `/capabilities` endpoint.

**Rationale**: Ollama is a local service, not a platform API. Metadata generation should be request-scoped (called during YouTube publish job), not a separate queued job. The service encapsulates retry logic and fallback templates. Keep it lightweight and testable with mocked HTTP calls.

**Implementation approach**:
- Use `httpx` (already in requirements.txt) for synchronous HTTP calls to Ollama.
- POST to `/api/generate` endpoint at `http://localhost:11434` (configurable via `APP_OLLAMA_BASE_URL`).
- Return structured JSON with title, description, tags; validate against output schema.
- Fallback to template-based metadata if Ollama unavailable or disabled.
- No retry loops here; let the calling job handle retries.

### 2. YouTube Publishing Service (Deliverable 2)
**Decision**: Create new `backend/services/youtube_publisher.py` that uses `google-auth-oauthlib` and `google-api-python-client` to authenticate and upload.

**Rationale**: YouTube is a formal platform API with OAuth2 flow and quota management. The service loads stored tokens from `PlatformConnection` (already in schema), handles token refresh, and delegates upload to Google API client. Integrate with existing `backend/services/platform_oauth.py` for token encryption/decryption.

**Implementation approach**:
- Load stored encrypted access token from `PlatformConnection` where `provider="youtube"` and `owner_id=<current>`.
- Use `google-auth-oauthlib.flow.InstalledAppFlow` to refresh token if expired (or direct refresh if we store refresh_token).
- Initialize `youtube = build("youtube", "v3", http=authorized_http_session)`.
- Create video with metadata (title, description, tags); upload via `videos().insert()`.
- Set privacy status to "unlisted" by default (not "private" because unlisted can be shared); return video_id and URL.
- Catch and classify errors: quota exceeded (recoverable), invalid credentials (permanent), invalid video file (permanent).

### 3. Lyric-Video Generator (Deliverable 3)
**Decision**: Create new `backend/services/lyric_video_generator.py` that extends `backend/services/video_rendering.py` patterns for FFmpeg filter generation and progress tracking.

**Rationale**: Lyric-video rendering combines existing audio with SRT/LRC subtitle overlays and optional waveform/spectrum visuals. Fits the video-rendering job type pattern. Reuse existing `render_motion_graphics()` infrastructure for FFmpeg subprocess management, progress file handling, and output validation.

**Implementation approach**:
- Add new job type `lyric_video_render` to job_runner.
- Parse LRC/SRT files into list of (start_ms, end_ms, text) tuples. Validate timing and text length.
- Build FFmpeg filter chain: `[0:a]showwaves=...` OR `showspectrum=...` for visual, overlay with subtitle stream from SRT.
- Use existing FFmpeg ASS subtitle format (or SRT if simpler); burn into video.
- Extend `VideoRender` model with columns: `platform_urls` (JSON), `metadata_json` (JSON), `publish_status`, `publish_error`.
- Fall back to rendering without subtitles if lyrics not provided or parsing fails.
- Progress tracking via FFmpeg progress file (extend existing pattern).

### 4. Schema Extensions (Deliverable 4)
**Decision**: Add new Pydantic schemas to `backend/domain/schemas.py` for metadata generation and YouTube publish requests/responses.

**Rationale**: Keep schema definitions centralized. New schemas follow existing patterns (BaseModel, Field validators, Literal enums for status).

**Implementation approach**:
- `MetadataGenerationRequest`: song_title, artist_name, duration_seconds, features (dict), mood (str).
- `MetadataGenerationResponse`: youtube_title (max 100), youtube_description (max 5000), youtube_tags (list[str], each max 500 total chars).
- `YouTubePublishRequest`: render_id, title, description, tags, is_public (default False).
- `YouTubePublishResponse`: video_id, url, platform="youtube", published_at (datetime).

### 5. Job Runner Extensions (Deliverable 5)
**Decision**: Extend `backend/services/job_runner.py` to handle two new job types: `lyric_video_render` and `youtube_publish`. Add job-level distinction between recoverable and permanent errors.

**Rationale**: New job types follow the existing pattern (load resources, call service, update DB state). Distinguish error types so retry logic doesn't retry permanent failures (invalid video, auth failure).

**Implementation approach**:
- `lyric_video_render` job: Load song asset + lyrics → call `lyric_video_generator` → update `VideoRender` with `publish_status="queued"` (ready for publish step).
- `youtube_publish` job: Load render → call `ollama_provider` for metadata → call `youtube_publisher` for upload → store video_id/URL in `platform_urls`, set `publish_status="published"`.
- Add `_classify_error(error_code)` to return `is_recoverable: bool` (network timeout, quota exceeded) vs permanent (invalid credentials, invalid video). Only retry on recoverable.

### 6. Database Schema Extensions (Deliverable 6)
**Decision**: Extend existing `VideoRender` model in `backend/domain/models.py` with four new columns: `platform_urls` (JSON), `metadata_json` (JSON), `publish_status` (enum-like string), `publish_error` (String).

**Rationale**: Reuse existing table pattern; no new table. Store platform URLs as JSON dict keyed by platform (youtube, instagram, facebook). Metadata is JSON snapshot of generated title/description/tags. Status tracks the publishing pipeline (queued → publishing → published/failed).

**Implementation approach**:
- Add columns: `platform_urls = Column(JSON, nullable=True, default=dict)`, `metadata_json = Column(JSON, nullable=True)`, `publish_status = Column(String(24), nullable=False, default="none")`, `publish_error = Column(String(255), nullable=True)`.
- Values for `publish_status`: "none" (new renders), "queued", "publishing", "published", "failed".
- Database migration: Use SQLAlchemy DDL approach (matching existing pattern where tables are created at startup from model definitions). Add migration comment in code if Alembic path is chosen later.

### 7. API Endpoints (Deliverable 7)
**Decision**: Add three new endpoints to `backend/routers/v1.py`: POST for queuing lyric-video render, POST for queuing YouTube publish, and extend GET `/capabilities` to include `youtube_publishing_available` and `ollama_available`.

**Rationale**: Endpoints follow existing patterns (owner-scoped, Depends(current_owner), rate limited, return SafeError on failure). Queue jobs via `AnalysisJob` with task_type, subject_id pointing to render_id.

**Implementation approach**:
- `POST /video/{render_id}/generate-lyric-video`: Validate render exists, create job with task_type="lyric_video_render", subject_id=render_id, return job status URL. Rate limit: 20/hour.
- `POST /video/{render_id}/publish-youtube`: Validate render exists and is in succeeded status, create job with task_type="youtube_publish", subject_id=render_id, return job status URL. Rate limit: 10/hour.
- `GET /capabilities`: Extend existing response to include `ollama_available: bool` (check if Ollama is reachable at startup/on-request), `youtube_publishing_available: bool` (check if YouTube OAuth credentials are configured).

### 8. Audit Logging (Deliverable 8)
**Decision**: Extend `backend/core/audit_logger.py` or add event logging directly in services to capture: lyric_video_generated, youtube_video_uploaded, metadata_generated_via_ollama, publish_failed.

**Rationale**: Follow existing audit logging pattern from Phase 4 plan (structured logs with owner_id, timestamps, no sensitive data).

**Implementation approach**:
- In `lyric_video_generator.py`, log "lyric_video_generated" event with render_id, duration_ms.
- In `youtube_publisher.py`, log "youtube_video_uploaded" event with render_id, video_id, url.
- In `ollama_provider.py`, log "metadata_generated_via_ollama" event with model, tokens_used.
- In job_runner, log "publish_failed" event with render_id, error_code, is_recoverable.

### 9. Tests (Deliverable 9)
**Decision**: Create five new test modules following existing test patterns.

**Rationale**: Each test file focuses on one service/feature, uses monkeypatch for mocks, test client for endpoints, skip guards for optional dependencies.

**Implementation approach**:
- `tests/test_ollama_provider.py`: Test connection, mock successful generation, test fallback, test prompt injection safety (verify output is JSON-structured, not arbitrary text).
- `tests/test_youtube_publisher.py`: Test OAuth token loading, mock successful upload, test metadata injection (verify title/description/tags are properly escaped), test error handling (quota, auth failure, invalid video), verify unlisted default.
- `tests/test_lyric_video_generation.py`: Test SRT parsing, test LRC parsing, test FFmpeg filter generation, test timing sync, test fallback when lyrics unavailable; skip if FFmpeg unavailable.
- `tests/test_job_runner_publishing.py`: Test `lyric_video_render` job execution (end-to-end), test `youtube_publish` job execution, test state transitions, test error recovery (only retry recoverable errors).
- `tests/test_e2e_publishing_workflow.py`: Full workflow: upload → analyze → lyric-video → YouTube (all services mocked), verify metadata flows through pipeline, verify URLs stored correctly.

### 10. Config Extensions (Deliverable 10)
**Decision**: Add new settings to `backend/config.py` for Ollama and YouTube.

**Rationale**: Follow existing config pattern (Pydantic BaseSettings, env_prefix="APP_", validation rules).

**Implementation approach**:
- Ollama: `ollama_base_url` (default "http://localhost:11434"), `ollama_model` (default "phi"), `ollama_enabled` (default True), `ollama_timeout_seconds` (default 30.0).
- YouTube: `youtube_upload_max_size_bytes` (default 1 GB = 1_000_000_000), `youtube_publish_rate_limit_per_hour` (default 10).
- Lyric video: `lyric_video_max_render_time_seconds` (default 300), `lyric_video_subtitle_format` (default "srt").
- Add production validation: If Ollama is enabled, check Ollama is reachable at startup (optional; warn if not).

### 11. Requirements (Deliverable 11)
**Decision**: Add four new packages to `requirements.txt`.

**Rationale**: Google and pysrt packages are stable, actively maintained, and widely used.

**Implementation approach**:
- Add: `google-auth-oauthlib>=1.1.0`, `google-auth-httplib2>=0.2.0`, `google-api-python-client>=2.100.0`, `pysrt>=1.1.2`.

### 12. README Update (Deliverable 12)
**Decision**: Extend `README.md` with setup instructions for Ollama and YouTube, and document rate limits and phase 5–8 test coverage.

**Rationale**: Help users configure and verify the new features.

**Implementation approach**:
- Add section "Ollama Local LLM Setup": Download and run Ollama, set `APP_OLLAMA_BASE_URL`, verify with `GET /capabilities`.
- Add section "YouTube Publishing Setup": Enable YouTube Data API, register OAuth app, set `APP_YOUTUBE_OAUTH_CLIENT_ID` etc., test with POST `/video/{render_id}/publish-youtube`.
- Add section "Lyric-Video Rendering": Upload lyrics file format (SRT/LRC), test with POST `/video/{render_id}/generate-lyric-video`.
- Document rate limits: 20/hour for lyric-video, 10/hour for YouTube publish.
- Update test coverage baseline for Phase 5–8.

---

## Implementation Order

Items are ordered by dependency and build order. Each item leaves the codebase in a buildable state.

### Phase 5a: Configuration & Schemas (Foundation)

- [ ] 1. Extend `backend/config.py` with Ollama and YouTube settings.
      Add: `ollama_base_url`, `ollama_model`, `ollama_enabled`, `ollama_timeout_seconds`, `youtube_upload_max_size_bytes`, `youtube_publish_rate_limit_per_hour`, `lyric_video_max_render_time_seconds`, `lyric_video_subtitle_format`.
      Files: `backend/config.py`, `requirements.txt` (add google-auth-oauthlib, google-auth-httplib2, google-api-python-client, pysrt)
      Verify: `python -c "from backend.config import settings; print(settings.ollama_base_url, settings.youtube_upload_max_size_bytes)"` — outputs default values.

- [ ] 2. Extend database schema: Add columns to `VideoRender` model.
      Add four columns: `platform_urls` (JSON), `metadata_json` (JSON), `publish_status` (String, default "none"), `publish_error` (String, nullable).
      Files: `backend/domain/models.py`
      Verify: Run `pytest tests/test_api_v1.py::test_v1_upload_analysis_and_report_flow -xvs` — confirms existing tests still pass and VideoRender schema is compatible.

- [ ] 3. Add Pydantic schemas for metadata and publishing.
      Add: `MetadataGenerationRequest`, `MetadataGenerationResponse`, `YouTubePublishRequest`, `YouTubePublishResponse` to `backend/domain/schemas.py`.
      Files: `backend/domain/schemas.py`
      Verify: `python -c "from backend.domain.schemas import MetadataGenerationResponse; print(MetadataGenerationResponse.model_json_schema())"` — confirms schema is valid.

### Phase 5b: Core Services (Ollama & YouTube)

- [ ] 4. Create Ollama LLM adapter service.
      New file `backend/services/ollama_provider.py` with:
      - `OllamaMetadata` dataclass: title, description, tags
      - `generate_metadata(song_title, artist_name, duration_seconds, features, mood) -> OllamaMetadata` function
      - POST to `{ollama_base_url}/api/generate` with prompt template
      - Return structured JSON or fallback to templates
      - Error handling: network timeout → fallback, Ollama disabled → fallback, invalid response → raise OllamaError
      Files: `backend/services/ollama_provider.py`
      Verify: `pytest tests/test_ollama_provider.py -xvs` — connection test, generation test, fallback test, injection safety test all pass.

- [ ] 5. Create YouTube publishing service.
      New file `backend/services/youtube_publisher.py` with:
      - `YouTubeVideo` dataclass: video_id, url, uploaded_at
      - `publish_to_youtube(render_id, access_token, title, description, tags, is_public, video_file_path) -> YouTubeVideo` function
      - Load credentials from config, authenticate with Google API
      - Upload video file, set metadata, return video_id and URL
      - Error handling: quota exceeded (YT_QUOTA_ERROR, recoverable), auth failure (YT_AUTH_ERROR, permanent), invalid file (YT_INVALID_VIDEO, permanent)
      Files: `backend/services/youtube_publisher.py`
      Verify: `pytest tests/test_youtube_publisher.py -xvs` — OAuth loading test, upload test (mocked), metadata injection test, error handling test, unlisted-default test all pass.

### Phase 5c: Lyric-Video Generator

- [ ] 6. Create lyric-video generator service.
      New file `backend/services/lyric_video_generator.py` with:
      - `parse_srt_file(path) -> list[Subtitle]` function (Subtitle: start_ms, end_ms, text)
      - `parse_lrc_file(path) -> list[Subtitle]` function
      - `build_ffmpeg_filter(lyrics, render_format) -> str` function (generates FFmpeg filter for showwaves/showspectrum + overlay)
      - `render_lyric_video(song_asset_path, lyrics_path, render_format, output_path) -> dict` function (calls FFmpeg, tracks progress, returns metadata)
      - Fallback: render without subtitles if lyrics unavailable or parsing fails
      - Integrate with existing video_rendering.py patterns for FFmpeg subprocess, progress file, output validation
      Files: `backend/services/lyric_video_generator.py`
      Verify: `pytest tests/test_lyric_video_generation.py -xvs` — SRT parsing, LRC parsing, filter generation, timing sync, fallback all pass; skip if FFmpeg unavailable.

### Phase 5d: Job Runner Extensions

- [ ] 7. Extend `backend/services/job_runner.py` to handle new job types.
      Add:
      - `_classify_error(error_code: str) -> (is_recoverable: bool)` helper
      - `_lyric_video_render_job(db: Session, job: AnalysisJob) -> None` function
      - `_youtube_publish_job(db: Session, job: AnalysisJob) -> None` function
      - Modify `run_v1_job()` to dispatch on task_type "lyric_video_render" and "youtube_publish"
      - For lyric_video_render: load VideoRender, load song asset, load lyrics if available, call lyric_video_generator, update render status
      - For youtube_publish: load VideoRender (must be succeeded status), load stored YouTube access token, call ollama_provider for metadata, call youtube_publisher for upload, store video_id in platform_urls, update publish_status
      - Retry logic: only retry if is_recoverable=True
      Files: `backend/services/job_runner.py`
      Verify: `pytest tests/test_job_runner_publishing.py -xvs` — job state transitions, error recovery, metadata flow all pass.

### Phase 5e: API Endpoints

- [ ] 8. Add API endpoints for lyric-video and YouTube publish.
      Modify `backend/routers/v1.py`:
      - `POST /video/{render_id}/generate-lyric-video` (owner-scoped, creates lyric_video_render job, rate limit 20/hour)
      - `POST /video/{render_id}/publish-youtube` (owner-scoped, creates youtube_publish job, rate limit 10/hour)
      - Extend `GET /capabilities` to return `ollama_available`, `youtube_publishing_available`
      Files: `backend/routers/v1.py`
      Verify: `pytest tests/test_api_v1.py -xvs` — verify existing tests pass; new endpoints tests in test_api_v1.py or separate test module verify job creation and status responses.

### Phase 5f: Audit Logging

- [ ] 9. Add audit logging for new events.
      Modify `backend/services/ollama_provider.py`, `backend/services/youtube_publisher.py`, `backend/services/lyric_video_generator.py`, `backend/services/job_runner.py`:
      - Log "lyric_video_generated" with render_id, duration_ms
      - Log "youtube_video_uploaded" with render_id, video_id, url
      - Log "metadata_generated_via_ollama" with model, response_tokens
      - Log "publish_failed" with render_id, error_code, is_recoverable
      Files: `backend/services/ollama_provider.py`, `backend/services/youtube_publisher.py`, `backend/services/lyric_video_generator.py`, `backend/services/job_runner.py`
      Verify: Run integration test and grep logs for expected event names and structures (no sensitive data).

### Phase 5g: Tests

- [ ] 10. Create comprehensive test suite.
      New files:
      - `tests/test_ollama_provider.py`: connection, generation, fallback, injection safety
      - `tests/test_youtube_publisher.py`: OAuth loading, upload (mocked), metadata injection, error handling, unlisted default
      - `tests/test_lyric_video_generation.py`: SRT/LRC parsing, filter generation, timing sync, fallback; skip if FFmpeg unavailable
      - `tests/test_job_runner_publishing.py`: job execution, state transitions, error recovery
      - `tests/test_e2e_publishing_workflow.py`: full pipeline with mocked services
      Files: `tests/test_*.py` (5 new files)
      Verify: Run `pytest tests/ -q` — all new tests pass, coverage >= 75% on new modules.

### Phase 5h: Documentation

- [ ] 11. Update README.md with setup and rate limit documentation.
      Add sections:
      - "Ollama Local LLM Setup": Download, run Ollama, set APP_OLLAMA_BASE_URL, test with /capabilities endpoint
      - "YouTube Publishing Setup": Enable API, register OAuth app, set credentials, test with endpoint
      - "Lyric-Video Rendering": Document SRT/LRC format, test workflow
      - Document rate limits: 20/hour lyric-video, 10/hour YouTube publish
      - Update phase 5–8 test coverage baseline
      Files: `README.md`
      Verify: Manual review — README is clear and complete.

---

## Cross-File Consistency & Naming Conventions

**Confirmed from codebase exploration:**

- Table naming: `v1_*` prefix for versioned tables (v1_jobs, v1_video_renders, etc.)
- Column naming: snake_case (owner_id, render_id, status, created_at, updated_at)
- Enum-like status values: lowercase strings ("queued", "running", "succeeded", "failed", "publishing", "published")
- Timestamps: always UTC with `utcnow()` function and `onupdate=utcnow` clause
- Error codes: UPPERCASE_SNAKE_CASE (RESOURCE_NOT_FOUND, INTERNAL_ERROR, YT_QUOTA_ERROR)
- Function names: snake_case, private functions prefixed with `_`
- Class names: PascalCase
- Import order: built-in, third-party, local (as seen in existing modules)
- Logging: use `logger = logging.getLogger(__name__)` at module level, structured logs with `extra` dict
- Rate limiting: use existing slowapi decorator pattern from Phase 4 (@limiter.limit("20/hour"))

---

## Risk Mitigation

### Risk: Ollama not running locally
**Mitigation**: Fallback to template-based metadata in ollama_provider. Graceful degradation — video renders and YouTube publishing still work, just with default/template metadata. Configuration option `APP_OLLAMA_ENABLED=false` to skip Ollama entirely.

### Risk: YouTube API quota exceeded during testing
**Mitigation**: Error code YT_QUOTA_ERROR is classified as recoverable; job will retry. In tests, mock YouTube publisher. Document quota limits in README (10k units/day for most APIs).

### Risk: FFmpeg not available on test environment
**Mitigation**: All video tests use `@pytest.mark.skipif(not shutil.which(...))` to skip gracefully if FFmpeg unavailable.

### Risk: Subtitle file parsing errors
**Mitigation**: Fallback to rendering without subtitles if SRT/LRC parsing fails. Log parsing error for debugging.

### Risk: OAuth token expiration during upload
**Mitigation**: YouTube publisher checks token expiration before upload, refreshes if needed using stored refresh_token. If refresh fails (user revoked), error is classified as permanent (permanent auth failure).

### Risk: Platform URLs overwrite in video renders
**Mitigation**: `platform_urls` is a JSON dict keyed by platform name ("youtube", "instagram", "facebook"). Publish to different platforms independently; dict merges, not overwrites.

---

## Verification Strategy

**Build verification**: After each item, run `pytest tests/ -q` to confirm no regressions.

**Integration verification**: After all items, run full test suite:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v --cov=backend --cov-report=term
```
Expected outcome: 50+ tests passing (40 existing + 10+ new), coverage >= 75% on new modules.

**Manual verification (phase 5–8 completion)**:
1. Start backend: `uvicorn backend.main:app --reload`
2. Check capabilities: `curl http://localhost:8000/api/v1/capabilities`
3. Create song, upload audio, request analysis (existing flow)
4. Queue lyric-video render: `curl -X POST http://localhost:8000/api/v1/video/{render_id}/generate-lyric-video`
5. Check job status: `curl http://localhost:8000/api/v1/jobs/{job_id}`
6. Queue YouTube publish: `curl -X POST http://localhost:8000/api/v1/video/{render_id}/publish-youtube`
7. Verify video_id stored in platform_urls

---

## Summary

This plan covers all 12 deliverables in dependency order, with concrete file paths, function/class names, and verification steps. No ambiguities remain; each item is independently actionable and testable. Implementation will follow the existing patterns established in Phases 1–4, ensuring consistency and maintainability.

**Key decisions made**:
- Ollama as a synchronous service (not a job type), called during YouTube publish job.
- YouTube as a formal platform service with OAuth token storage and refresh.
- Lyric-video as a new job type (`lyric_video_render`) extending existing video_rendering patterns.
- All new metadata stored in `VideoRender` table extensions (no new tables).
- Error classification (recoverable vs. permanent) for intelligent retry behavior.
- Comprehensive test coverage with mocked external services and skip guards for optional dependencies.

