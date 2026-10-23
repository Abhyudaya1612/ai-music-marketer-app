# Phase 4 Security & Production Readiness Implementation Plan

## Investigation Findings

### 1. Authentication & Authorization: MEDIUM severity issues

**Findings:**
- Bearer token validation: Uses HMAC constant-time comparison (`hmac.compare_digest`) in `backend/core/auth.py` — **GOOD**
- Single workspace model: `APP_API_TOKEN` and `APP_AUTH_USER_ID` are global; all requests run as one `owner_id` — **BY DESIGN**
- Owner-scoped access: All queries filter by `owner_id` from `current_owner()` dependency — **GOOD**
- Token lifetime: No expiration or rotation mechanism; token is static credential — **MEDIUM ISSUE**
- No rate limiting on auth: `/session`, `/health`, `/ready`, `/capabilities` endpoints unprotected — **HIGH ISSUE**

**Decision:** Token rotation and expiration not required for single-workspace local app, but rate limiting is essential.

### 2. Upload Validation: LOW severity (mostly good)

**Findings:**
- File size limits: Checked twice (intent + upload stream) at `settings.max_upload_bytes` (50 MB) — **GOOD**
- MIME type checks: Content-Type validated against audio/* or application/octet-stream in `create_upload_intent()` — **GOOD**
- FFprobe validation: Full validation in `verify_audio()` checks format, duration limit (900s), audio stream presence — **GOOD**
- Temp file cleanup: Uses `.part` files, atomically moved on success, unlinked on failure — **GOOD**
- Size mismatch detection: Declared size vs actual upload size checked in `write_upload()` — **GOOD**
- Path traversal protection: `asset_directory()` validates UUID and resolves against `storage_root()` — **GOOD**

**Decision:** Upload validation is solid. No changes needed.

### 3. Private Media Storage: LOW severity (mostly good)

**Findings:**
- Storage location: `settings.media_storage_path` defaults to `./private-media`, not in web root — **GOOD**
- Path traversal prevention: `asset_directory()` parses UUID, resolves, and validates parent is `storage_root()` — **GOOD**
- File permissions: Files created with default OS permissions (0o644 on Unix, inherited on Windows) — **ADEQUATE**
- Direct download: `/video-renders/{render_id}/download` returns `FileResponse` from private-media directory — **GOOD**

**Decision:** Media storage is properly isolated. No changes needed.

### 4. Consent & Rights Enforcement: LOW severity (good implementation)

**Findings:**
- Consent checks: `has_active_consent()` in `backend/services/consent.py` checks scope (song-specific or workspace-wide) — **GOOD**
- Rights checks: `_require_audio_authorization()` and `_require_analysis_authorization()` check both rights declaration and consent before upload/analysis — **GOOD**
- Withdrawal blocks processing: Consent withdrawal logic in `POST /consents/{consent_id}/withdraw` disconnects platform accounts — **GOOD**
- Job-time consent re-check: `_video_render_job()` re-checks consent during rendering via `authorization_is_active()` — **GOOD**
- Consent withdrawal during job: If consent withdrawn mid-render, job fails with `CONSENT_REQUIRED` — **GOOD**

**Decision:** Consent enforcement is solid. No changes needed.

### 5. Error Responses: MEDIUM severity

**Findings:**
- Stack traces: `ApiError` handler in `backend/core/errors.py` returns only error code, message, request_id — **GOOD**
- Safe error messages: `_error()` in `backend/routers/v1.py` maps error codes to safe messages only — **GOOD**
- No sensitive data leakage: No passwords, tokens, paths, or personal data in responses — **GOOD**
- Validation errors: `RequestValidationError` handler in `main.py` returns field name, message, type — **GOOD**
- HTTP exception handler: Maps HTTPException to API error format — **GOOD**
- Request ID tracking: Middleware adds X-Request-ID header for tracing — **GOOD**
- **BUT:** No explicit 5xx error handler; unhandled exceptions may leak details — **MEDIUM ISSUE**

**Decision:** Add explicit 500 handler to catch unhandled exceptions and return safe message.

### 6. CORS Configuration: LOW severity (appropriate for local dev)

**Findings:**
- CORS setup: `CORSMiddleware` in `main.py` uses `settings.cors_origin_list` from `APP_CORS_ORIGINS` — **GOOD**
- Default origins: Defaults to `["*"]` if not configured — **BY DESIGN for local**
- Credentials: `allow_credentials=True` with `allow_origins=["*"]` — **NOT ALLOWED by CORS spec**
- Methods & headers: `allow_methods=["*"]`, `allow_headers=["*"]` — **BY DESIGN for dev**

**Decision:** CORS is permissive by design for local dev. In production, must set explicit origins and disable wildcard with credentials.

### 7. Configuration & Secrets: MEDIUM to HIGH severity

**Findings:**
- `.env` loading: Uses Pydantic `BaseSettings` with `env_prefix="APP_"` — **GOOD**
- Secret types: `token_encryption_key` and OAuth secrets use `SecretStr` — **GOOD**
- Required secrets: `APP_API_TOKEN` is required in Docker env (marked `:?Set APP_API_TOKEN`) — **GOOD**
- Hardcoded defaults: `api_token=""` (empty default), `auth_user_id="local-artist"` — **ISSUE**
- Debug mode: `APP_ENVIRONMENT` exists but not used to disable debug features — **MEDIUM ISSUE**
- Token encryption: `token_encryption_key` defaults to empty string — **HIGH ISSUE** (oauth tokens unencrypted or encryption broken)
- AI provider secrets: `APP_OPENROUTER_API_KEY`, `APP_OPENROUTER_MODEL` optional but no validation — **MEDIUM ISSUE**

**Decision:** Add validation in config to fail fast on missing secrets in production, warn on empty encryption key.

### 8. Docker & Deployment: MEDIUM severity

**Findings:**
- Dockerfile: Not found; `docker-compose.yml` references `Dockerfile` but it doesn't exist — **CRITICAL ISSUE**
- Docker Compose: Uses volumes `/data` for SQLite and `/data/private-media` — **GOOD**
- Environment passing: Passes `APP_API_TOKEN`, `APP_AI_PROVIDER`, etc. via `environment:` — **GOOD**
- Restart policy: `restart: unless-stopped` — **GOOD**
- Non-root user: Not specified in compose or Dockerfile — **ISSUE** (will run as root)
- Exposed ports: `8000` (backend), `3000` (frontend) — **GOOD for local**
- Database in volume: SQLite at `/data/music_marketer.db` — **GOOD**

**Decision:** Create Dockerfile with non-root user, minimal base image, security best practices.

### 9. Health & Readiness Endpoints: MEDIUM severity

**Findings:**
- `/health` endpoint: Returns `{"status": "ok"}` without dependencies — **BASIC**
- `/ready` endpoint: Checks DB connectivity — **GOOD**
- No liveness probe: Container may be zombie if scheduler crashes — **MEDIUM ISSUE**
- No metrics endpoint: No way to observe request rate, latency — **LOW ISSUE for Phase 4**
- Scheduler startup/shutdown: `start_scheduler()` and `stop_scheduler()` in lifespan context manager — **GOOD**

**Decision:** Add liveness check for scheduler health.

### 10. Background Scheduler: MEDIUM severity

**Findings:**
- Scheduler start: `BackgroundScheduler` from APScheduler, started in lifespan `async` context — **GOOD**
- Polling loop: `_dispatch_queued_jobs()` runs every `job_poll_interval_seconds` (default 5) — **GOOD**
- Atomic job claiming: Uses UPDATE to transition job from 'queued' to 'running' — **GOOD for single instance**
- Stale job recovery: Jobs stuck in 'running' > `job_idle_timeout_seconds` (300s default) requeued — **GOOD**
- Max attempts: `job_max_attempts` default 3 — **GOOD**
- Multi-instance concern: No distributed lock; two instances could claim same job — **ISSUE for multi-instance**
- Error handling: Catches exceptions, logs, doesn't crash scheduler — **GOOD**

**Decision:** Multi-instance operation not supported without Celery/Redis. Document as single-instance only. Add scheduler health check.

### 11. Frontend Integration: NOT TESTABLE without running application

**Findings:**
- Frontend structure: Only `app/layout.tsx` and `app/page.tsx` found (minimal Next.js setup)
- Cannot verify without running frontend
- Will need to verify during test phase

**Decision:** Testing deferred to later steps.

### 12. CI/CD: MEDIUM severity

**Findings:**
- Test job: Installs Python 3.11, FFmpeg, essentia (optional, continues on error) — **GOOD**
- Audio tests: Both use `@pytest.mark.skipif` on FFmpeg/FFprobe availability — **GOOD**
- Video tests: No skip markers found in grep search (may not have special skip logic) — **ISSUE** (need to check)
- Coverage reporting: Uses codecov-action — **GOOD**
- Frontend: Type-check and build attempts with `|| true` (continues on error) — **GOOD**

**Decision:** Verify video test status and ensure they have proper skip markers.

---

## Implementation Plan

### Phase 4a: Rate Limiting (HIGH PRIORITY)

**Rationale:** Sensitive endpoints (`/api/v1/consents`, `/api/v1/analyses`, `/upload`) can be abused to exhaust storage, compute, or create denial-of-service. Single-user local app means we can use in-process rate limiting without Redis.

**Items:**

1. **Add rate-limiting middleware using slowapi**
   - Files to modify: `backend/main.py`, `backend/config.py`, `requirements.txt`
   - Files to create: None
   - Rate limits:
     - `/api/v1/consents`: 10 per minute per endpoint
     - `/api/v1/consents/{id}/withdraw`: 10 per minute
     - `/api/v1/analyses`: 5 per minute (resource-intensive)
     - `/api/v1/songs/{id}/assets/complete`: 5 per minute (triggers background job)
     - `/api/v1/assets/{id}/upload`: 10 per minute (large file uploads)
     - `/api/v1/video-renders`: 5 per minute
     - `/api/v1/session`: 30 per minute (auth check)
     - All other endpoints: 100 per minute (safe default)
   - Return `429 Too Many Requests` with Retry-After header
   - Key by owner_id where authenticated, IP address for unauthenticated
   - Config: `APP_RATE_LIMIT_ENABLED=true` (default), `APP_RATE_LIMIT_STORAGE=memory`
   - Verify: Run unit test checking 429 responses on repeated requests

2. **Document rate limits in error responses**
   - Files to modify: `backend/routers/v1.py` (SafeError enum or constant)
   - Add Retry-After header calculation and inclusion in 429 responses
   - Verify: Check that 429 response includes X-RateLimit-* headers

---

### Phase 4b: Audit Logging (HIGH PRIORITY)

**Rationale:** Track security events (auth failures, consent changes, analysis requests, video rendering) for forensics and abuse detection. Never log passwords, tokens, or raw audio.

**Items:**

1. **Add structured security event logging**
   - Files to modify: `backend/main.py`, `backend/core/auth.py`, `backend/routers/v1.py`, `backend/services/job_runner.py`, `backend/services/consent.py`
   - Events to log:
     - Auth success/failure (owner_id, timestamp)
     - Consent grant/withdrawal (owner_id, song_id, consent_type)
     - Rights declaration (owner_id, song_id)
     - Upload initiated/completed/failed (asset_id, size_bytes, duration)
     - Analysis requested/completed/failed (analysis_id, provider, duration)
     - Video render requested/completed/failed (render_id, format)
     - Job failures (job_id, error_code, task_type)
     - Consent checked mid-job and denied (job_id, reason)
   - Format: JSON with timestamp, event_type, owner_id, details, no sensitive data
   - Use `logger.info()` with structured `extra` dict (already partially done)
   - Config: `APP_AUDIT_LOG_LEVEL=INFO` (default), output to stdout via logging config
   - Verify: Run unit tests and check logs contain expected events without secrets

---

### Phase 4c: Configuration & Secrets Hardening (HIGH PRIORITY)

**Rationale:** Production deployments must fail fast and safely when required secrets are missing or insecure defaults are detected.

**Items:**

1. **Add production config validation**
   - Files to modify: `backend/config.py`
   - Validation rules:
     - In production env: `APP_API_TOKEN` must be set (non-empty) and 32+ chars
     - In production env: `APP_TOKEN_ENCRYPTION_KEY` must be set and valid Fernet key
     - In production env: `APP_DATABASE_URL` must not use SQLite
     - In production env: `APP_CORS_ORIGINS` must be explicit (not `*`)
     - In production env: `APP_ENVIRONMENT` must be "production" (case-insensitive)
     - Warning if AI provider secrets are configured but insecurely (empty values)
   - Fail on startup with clear error message if validation fails
   - Verify: Set APP_ENVIRONMENT=production without required secrets and confirm startup error

2. **Document required and optional secrets**
   - Files to modify: `.env.example`
   - Add comments clarifying:
     - Which secrets are required for production
     - Which are optional for local development
     - Token encryption key generation command
     - Format and validation rules
   - Verify: Manual review of updated `.env.example`

---

### Phase 4d: Error Handling (MEDIUM PRIORITY)

**Rationale:** Unhandled exceptions in endpoint or background handlers should never leak stack traces or internal details.

**Items:**

1. **Add generic 500 error handler**
   - Files to modify: `backend/main.py`, `backend/core/errors.py`
   - Add global exception handler that catches all unhandled exceptions and returns safe 500 response
   - Log full exception and traceback to debug logs (not returned to client)
   - Response: `{"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "request_id": "...", "details": []}}`
   - Verify: Trigger unhandled exception and confirm 500 response without stack trace

---

### Phase 4e: Docker & Deployment Hardening (MEDIUM PRIORITY)

**Rationale:** Dockerfile missing; container must run non-root, use minimal base image, and configure for security.

**Items:**

1. **Create Dockerfile with security best practices**
   - Files to create: `Dockerfile`
   - Use Python 3.11-slim as base (minimal, regularly updated)
   - Install FFmpeg and FFprobe from system packages
   - Create non-root `appuser` with UID 1000
   - Copy requirements.txt and install dependencies
   - Copy source code to `/app`
   - Set working directory to `/app`
   - Expose port 8000
   - Health check: `curl -f http://localhost:8000/api/ready || exit 1`
   - CMD: `["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]`
   - User: `appuser`
   - No ENTRYPOINT override, no shell
   - Verify: Build image, run container, confirm non-root user and health check passes

2. **Update docker-compose.yml for production readiness**
   - Files to modify: `docker-compose.yml`
   - Add healthcheck to backend service (interval 30s, timeout 5s, retries 3)
   - Add resource limits: `mem_limit: "1g"`, `cpus: "1"`
   - Set logging driver to json-file with max-size and max-file rotation
   - Use explicit image names and versions (not latest)
   - Verify: Run docker-compose up, confirm health checks pass

---

### Phase 4f: Scheduler Health & Liveness (MEDIUM PRIORITY)

**Rationale:** Scheduler may crash or become unresponsive; health endpoint should detect it.

**Items:**

1. **Add scheduler liveness check**
   - Files to modify: `backend/services/job_scheduler.py`, `backend/routers/v1.py`
   - Add `get_scheduler_health()` function returning last dispatch timestamp and age in seconds
   - Modify `/ready` endpoint to check scheduler status (if enabled)
   - Verify: Add endpoint test confirming scheduler marked unhealthy if no dispatch > 2x poll interval

---

### Phase 4g: Frontend Verification (DEFERRED - requires running application)

**Rationale:** Cannot verify frontend integration without running application and browser testing.

**Items:**

1. **Manual verification script (to be run in next step)**
   - Test endpoints: Create song → Upload audio → Verify asset → Request analysis → Check report
   - Test auth: Request without token, invalid token, valid token
   - Test consent: Try analysis without consent, grant consent, try again
   - Test error handling: Invalid JSON, oversized file, expired upload intent
   - Verify: Each test returns appropriate HTTP status and response format

---

### Phase 4h: CI/CD Verification (DEFERRED - requires GitHub access)

**Rationale:** Cannot inspect actual CI runs without GitHub access or local GitHub Actions environment.

**Items:**

1. **Document CI test configuration**
   - Files to review: `.github/workflows/ci.yml`
   - Verify: Check that audio and video tests are properly marked with skipif decorators

---

## Summary of Changes

| Phase | Component | Change Type | Files | Severity |
|-------|-----------|-------------|-------|----------|
| 4a | Rate Limiting | Add middleware | `main.py`, `config.py`, `requirements.txt` | HIGH |
| 4b | Audit Logging | Add event logging | `auth.py`, `v1.py`, `job_runner.py`, `consent.py`, `config.py` | HIGH |
| 4c | Secrets | Add validation | `config.py`, `.env.example` | HIGH |
| 4d | Error Handling | Add 500 handler | `main.py`, `errors.py` | MEDIUM |
| 4e | Docker | Create Dockerfile, update compose | `Dockerfile`, `docker-compose.yml` | MEDIUM |
| 4f | Scheduler | Add liveness check | `job_scheduler.py`, `v1.py` | MEDIUM |
| 4g | Frontend | Manual test (no code change) | None | DEFERRED |
| 4h | CI/CD | Verify (no code change) | None | DEFERRED |

## Verification Plan

Each item includes specific verification steps using pytest, curl, or manual inspection:
- Rate limiting: pytest 429 response test
- Audit logging: Check log output for expected events
- Secrets validation: Startup test with missing secrets
- Error handling: Trigger exception, verify response
- Docker: Build image, run container, check health
- Scheduler: Liveness endpoint test
- Frontend: Manual E2E test
- CI/CD: GitHub Actions inspection

No code changes will break existing functionality. All changes are additive or hardening.

## Execution Order

1. Phase 4c: Config validation (prerequisite for production)
2. Phase 4a: Rate limiting (protect from abuse)
3. Phase 4b: Audit logging (observe security events)
4. Phase 4d: Error handling (prevent information leakage)
5. Phase 4e: Docker (deployment security)
6. Phase 4f: Scheduler health (operational readiness)
7. Phase 4g: Frontend verification (manual test)
8. Phase 4h: CI/CD verification (documentation)

