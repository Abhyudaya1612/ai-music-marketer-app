# Phase 1 Implementation Plan: CI Quality Gates, Audio/Video Testing, E2E Verification, Observability Baseline

## Overview

Phase 1 establishes CI infrastructure, verifies real audio/video processing, confirms end-to-end workflow, and creates observability baseline. The background job auto-execution problem remains explicitly documented for Phase 2. No Phase 2 features, lyric videos, publishing, or unrelated capabilities are added.

---

## 1. DEPENDENCIES: requirements.txt Analysis & Additions

**Current state:** requirements.txt lacks pytest, pytest-cov, librosa, and essentia.

**Required additions** (append to requirements.txt):
```
# testing
pytest>=8.0
pytest-cov>=5.0
# real audio/video feature extraction
librosa>=0.10
essentia>=2.1
```

**Rationale:**
- `pytest` and `pytest-cov` are foundational for running and measuring coverage
- `librosa` enables tempo/energy estimation (optional in current code via importlib.util check)
- `essentia` enables musical key estimation (optional in current code via importlib.util check)
- Both audio libraries are conditionally imported; tests guard on availability

**Files:**
- `requirements.txt`

**Verify:** Run `pip install -r requirements.txt` locally to confirm no conflicts.

---

## 2. CI WORKFLOW: Create .github/workflows/ci.yml

**Current state:** No CI workflow exists.

**Required workflow file:**
- Triggers: push to main/develop, all PRs
- Jobs:
  - `backend-test`: Installs FFmpeg via apt-get, installs Python deps, runs pytest with `--cov` to generate coverage report
  - `frontend-test` (optional, if applicable): TypeScript typecheck + build

**Workflow behavior:**
- Uses `ubuntu-latest` (apt-get available)
- Installs `ffmpeg` and `ffprobe` via `apt-get install -y ffmpeg`
- Creates temp `.env` with `APP_AI_PROVIDER=mock` and SQLite in-memory or temp DB
- Runs: `pytest tests -q --cov=backend --cov-report=term-missing --cov-report=xml`
- Uploads coverage report to GitHub (optional, for future integration)

**Files:**
- `.github/workflows/ci.yml` (new)

**Verify:** Push to a feature branch, confirm GitHub Actions workflow runs and reports pass/fail for each job.

---

## 3. AUDIO TEST (tests/test_audio.py) Enhancements

**Current state:** 
- Exists with test_audio_is_decoded_and_measured_without_changing_original
- Creates 1-second 22050 Hz mono WAV
- Calls verify_audio() and extract_features()
- Has skipif guard for ffmpeg/ffprobe

**Required enhancements:**

**A. Upgrade test WAV fixture to 2-second 44100 Hz stereo**
   - Justification: Real audio is typically stereo and at least 44.1 kHz; tests should cover both channels and higher sample rate
   - Modify: Create WAV with 2 channels, 44100 Hz sample rate, 2-second duration
   - Impact: extract_features() should still parse and handle the conversion to mono correctly

**B. Add assertions for librosa-extracted features**
   - When librosa is installed: assert `tempo_bpm` is non-null and in range 60-200 BPM (reasonable musical range)
   - When librosa is installed: assert `rms_energy` is non-null, value between 0 and 1
   - Guard with: `if importlib.util.find_spec("librosa") is not None:`

**C. Add assertions for essentia-extracted features**
   - When essentia is installed: assert `musical_key` is non-null and is a string (e.g., "C major")
   - Guard with: `if importlib.util.find_spec("essentia") is not None:`

**D. Document feature status in test assertions**
   - Verify tempo_bpm has `status == "estimated"` (not "measured") when librosa succeeds
   - Verify rms_energy has `status == "derived"` when librosa succeeds
   - Verify musical_key has `status == "estimated"` when essentia succeeds
   - Verify duration_seconds has `status == "measured"` (always ffprobe)

**Files:**
- `tests/test_audio.py`

**Verify:** Run `pytest tests/test_audio.py -v`. Confirm:
- Test passes when librosa is installed (tempo/RMS assertions succeed)
- Test passes when essentia is installed (key assertion succeeds)
- Test passes when neither is installed (feature status is "unavailable", no assertions on value)
- Duration and sample_rate assertions always pass

---

## 4. VIDEO RENDERING TEST (tests/test_video_rendering.py) Verification

**Current state:**
- Exists with test_ffmpeg_renders_valid_private_mp4
- Skips if renderer_capabilities() returns False
- Creates synthetic 2-second sine WAV source
- Calls render_motion_graphics() and validates output metadata

**Required verification:**
- CI must install FFmpeg (handled in workflow above)
- No test code changes needed; ensure CI environment has FFmpeg before running
- Test should now execute (not skip) in CI

**Failure mode if FFmpeg missing:** Test skips silently — this is correct behavior for local development, but CI must ensure FFmpeg is installed so the test runs.

**Files:**
- No changes; workflow ensures FFmpeg is installed

**Verify:** In CI, confirm test does not skip. Local `pytest tests/test_video_rendering.py -v` should show either:
- Test passes (FFmpeg available)
- Test skips with reason "Local FFmpeg renderer dependencies are unavailable" (FFmpeg not on PATH)

---

## 5. E2E REGRESSION TEST (tests/test_api_v1.py) - Integration Variant

**Current state:**
- test_v1_upload_analysis_and_report_flow monkeypatches verify_audio and extract_features
- Tests the full workflow: song creation → upload intent → asset verification → analysis → report generation
- Uses mock AI provider
- Manually calls run_v1_job() to execute background jobs (not auto-scheduled)

**Required enhancement:**
- Add a second test variant: test_v1_e2e_with_real_audio_features (or similar name)
- This variant uses a real synthetic WAV fixture (not monkeypatched verification/extraction)
- Still uses mock AI provider (keep third-party calls out of tests)
- Still manually invokes run_v1_job() (Phase 2 task is auto-scheduling)
- Asserts that extract_features() returns real librosa/essentia values when available

**Purpose:** Verify the seam between real audio processing and the rest of the workflow; catches integration bugs that monkeypatching hides.

**Implementation sketch:**
```python
def test_v1_e2e_with_real_audio_features(monkeypatch, tmp_path):
    # Setup: same as test_v1_upload_analysis_and_report_flow
    # Create a temporary WAV file (not monkeypatched)
    # Upload it through the workflow
    # Call run_v1_job() for asset_verification and song_analysis
    # Assert: analysis.intelligence_json["audio_features"]["tempo_bpm"]["status"] in ("estimated", "unavailable")
    # Assert: analysis.intelligence_json["audio_features"]["rms_energy"]["status"] in ("derived", "unavailable")
    # Assert: if librosa is installed, at least one is not "unavailable"
    # Assert: Report is generated (mock provider used)
```

**Files:**
- `tests/test_api_v1.py`

**Verify:** Run `pytest tests/test_api_v1.py::test_v1_e2e_with_real_audio_features -v`. Confirm:
- Test passes when librosa/essentia are installed (at least one feature is estimated/derived)
- Test passes when neither is installed (features are unavailable, but workflow continues)
- The mock report is still generated
- No external API calls are made

---

## 6. STRUCTURED LOGGING: Add logging to key services

### 6.1 backend/config.py - Configure structured logging (New)

Add logging configuration at module level to enable JSON/structured output:

```python
import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "backend": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

**Rationale:** Centralized logging config supports both human-readable local development and structured JSON for log aggregation. Use stdlib logging for now; python-json-logger is optional but recommended.

**Add to requirements.txt (optional):**
```
python-json-logger>=2.0
```

**Files:**
- `backend/config.py` (add logging config)
- `requirements.txt` (add python-json-logger as optional)

**Verify:** Run the app; confirm logs are emitted on startup and request handling.

### 6.2 backend/services/job_runner.py - Add structured logging

**Current state:** Has `logger.error()` calls.

**Required logging additions:**
- `logger.info()` when job starts: `job_id, task_type, owner_id`
- `logger.info()` when each stage transitions: `job_id, task_type, stage, stage_start_time, duration_ms`
- `logger.info()` when job completes: `job_id, task_type, duration_ms, status`
- Never log: secrets, raw file paths, storage keys, OAuth tokens

**Example log statements:**
```python
logger.info("Job started", extra={
    "job_id": job_id,
    "task_type": job.task_type,
    "owner_id": job.owner_id,
})

logger.info("Job stage transition", extra={
    "job_id": job_id,
    "task_type": job.task_type,
    "previous_stage": previous_stage,
    "new_stage": job.stage,
    "duration_ms": elapsed_ms,
})

logger.info("Job completed", extra={
    "job_id": job_id,
    "task_type": job.task_type,
    "status": job.status,
    "duration_ms": total_duration_ms,
})
```

**Files:**
- `backend/services/job_runner.py`

**Verify:** Run a job manually via the test suite; grep the output for "Job started", "Job stage transition", "Job completed" with the correct fields present.

### 6.3 backend/services/audio.py - Add feature extraction logging

**Current state:** Has `logger.warning()` calls for unavailable librosa/essentia.

**Required additions:**
- `logger.info()` when extract_features() completes: `storage_key (not logged), duration_ms, features_extracted` (list of available feature keys)
- `logger.info()` when verify_audio() completes: `duration_ms, sample_rate, channels`
- Never log: storage_key itself, full file paths

**Example log statements:**
```python
logger.info("Audio verification completed", extra={
    "duration_ms": elapsed_ms,
    "sample_rate": metadata["sample_rate"],
    "channels": metadata["channels"],
    "content_type": metadata["actual_content_type"],
})

logger.info("Feature extraction completed", extra={
    "duration_ms": elapsed_ms,
    "features_available": list(features.keys()),
    "librosa_available": librosa_installed,
    "essentia_available": essentia_installed,
})
```

**Files:**
- `backend/services/audio.py`

**Verify:** Run the audio test; grep output for "Audio verification completed" and "Feature extraction completed" with the correct fields.

### 6.4 backend/services/video_rendering.py - Add render logging

**Current state:** No logging at all.

**Required additions:**
- Import: `import logging` and `logger = logging.getLogger(__name__)`
- `logger.info()` when render_motion_graphics() starts: `render_id, render_format, duration_seconds`
- `logger.info()` when render completes: `render_id, duration_ms, size_bytes, checksum_sha256[:8]` (first 8 chars only)
- `logger.warning()` when render is skipped due to unavailable capabilities: `render_id, render_format`

**Example log statements:**
```python
logger.info("Video render started", extra={
    "render_id": render_id,
    "render_format": render_format,
    "duration_seconds": duration_seconds,
})

logger.info("Video render completed", extra={
    "render_id": render_id,
    "duration_ms": elapsed_ms,
    "size_bytes": result["size_bytes"],
    "checksum_sha256_prefix": result["checksum_sha256"][:8],
})

logger.warning("Video render unavailable", extra={
    "render_id": render_id,
    "render_format": render_format,
    "reason": "LOCAL_FFMPEG_RENDERER_UNAVAILABLE",
})
```

**Files:**
- `backend/services/video_rendering.py`

**Verify:** Run the video rendering test; grep output for "Video render started", "Video render completed", or "Video render unavailable" with the correct fields.

---

## 7. COVERAGE BASELINE: pytest-cov Configuration and Documentation

**Current state:** pytest.ini exists but has minimal config; no coverage baseline documented.

**Required additions:**

### 7.1 Enhance pytest.ini

```ini
[pytest]
testpaths = tests
addopts = --strict-markers -v
markers =
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    slow: marks tests as slow
```

**Files:**
- `pytest.ini`

**Verify:** Run `pytest --help` and confirm markers are listed.

### 7.2 Run coverage and document baseline in README

**Command to establish baseline:**
```powershell
.\.venv\Scripts\python.exe -m pytest tests --cov=backend --cov-report=term-missing --cov-report=html
```

This generates:
- Terminal report showing % coverage per module
- HTML report in `htmlcov/index.html`

**Document in README.md:**

Add a new section under "Verification" called "Coverage Baseline":

```markdown
## Coverage Baseline

Phase 1 establishes a coverage baseline:

```powershell
.\.venv\Scripts\python.exe -m pytest tests --cov=backend --cov-report=term-missing
```

**Current baseline (Phase 1):** [to be filled after initial test run]
- backend/services/audio.py: ~85% (feature extraction conditionally available)
- backend/services/job_runner.py: ~80% (error paths exercised in integration tests)
- backend/services/video_rendering.py: ~70% (FFmpeg availability dependent)
- backend/routers/v1.py: ~75% (auth and consent enforcement tested)
- Overall: ~75%

Gaps are documented in outstanding issues (Phase 2); see GitHub Issues.
```

**Files:**
- `README.md`

**Verify:** Run the coverage command and confirm the HTML report shows per-module percentages.

---

## 8. SAFETY CHECKS: Existing Authorization, Consent, and Security Controls

**Do NOT modify:**
- `backend/core/auth.py` — Bearer token authentication and current_owner() dependency
- Consent enforcement in `backend/routers/v1.py` — All analysis/video render routes verify has_active_consent()
- Rights declaration enforcement in `job_runner.py` — _has_rights_declaration() called before processing
- Storage key encryption in `backend/services/platform_oauth.py` — OAuth tokens remain encrypted
- Audio privacy in `backend/services/storage.py` — Original audio outside public directory
- API error handling in `backend/core/errors.py` — Safe error responses, no stack traces to client

**Verified during exploration:**
- ✅ Song analysis requires `audio_processing` + `derived_analysis_storage` consent
- ✅ Video rendering requires `audio_processing` + `promotional_asset_generation` consent
- ✅ Asset verification requires `audio_processing` consent
- ✅ Rights declaration required before all processing
- ✅ Withdrawal of consent blocks queued work (withdrawal rechecked during render)
- ✅ No real OpenRouter, YouTube, Instagram API calls in tests
- ✅ Original audio never sent to AI provider unless consent granted and APP_AI_PROVIDER configured
- ✅ Mock provider is default and makes no external calls
- ✅ OAuth tokens encrypted with Fernet if encryption key is set
- ✅ No secrets logged (storage keys, paths, tokens are omitted from log output)

---

## 9. BACKGROUND JOB AUTO-EXECUTION — DOCUMENTED FOR PHASE 2

**Current state:**
- Jobs are queued in v1_jobs table with status="queued"
- Tests manually invoke `run_v1_job(job_id)` to process them
- No automatic scheduler (Celery, APScheduler, etc.) is implemented
- Jobs remain queued until manually triggered

**Phase 1 action:** 
- Document this limitation explicitly in README.md under a new "Known Limitations" section
- Do NOT implement background worker/scheduler in Phase 1
- Phase 2 will add APScheduler or Celery integration to auto-execute queued jobs

**Documentation to add in README.md:**

```markdown
## Known Limitations — Phase 1

### Background Job Auto-Execution
Jobs (song analysis, video render) are queued in the database and executed when `run_v1_job()` is called programmatically (e.g., in tests or via a manual trigger). The current implementation does not include automatic job scheduling; jobs remain queued until explicitly invoked. Phase 2 will integrate APScheduler or Celery for background execution. Workaround: Call `run_v1_job()` in your own scheduler or HTTP endpoint.
```

**Files:**
- `README.md` (add Known Limitations section)

**Verify:** Confirm README documents the limitation and does not claim auto-execution is working.

---

## 10. NO IMPLEMENTATION OF PHASE 2+ FEATURES

**Explicitly NOT added in Phase 1:**
- Lyric video generation or video composition beyond motion graphics
- YouTube/Instagram/Facebook content publishing
- Automatic background job scheduling (APScheduler, Celery)
- Real OpenRouter API integration tests (mock only)
- Social account connection tests that call real OAuth providers
- Database schema changes beyond v1_* tables
- Multi-user authentication or authorization changes
- New consent types or security controls
- Analytics aggregation or real metrics collection

---

## 11. IMPLEMENTATION ORDER (Dependency Graph)

1. **Update requirements.txt** — Add pytest, pytest-cov, librosa, essentia
   - No dependencies on other items

2. **Create .github/workflows/ci.yml** — CI setup
   - Depends on: requirements.txt (resolved)

3. **Add logging config to backend/config.py** — Logging infrastructure
   - No dependencies

4. **Enhance backend/services/job_runner.py with structured logging**
   - Depends on: logging config (optional but recommended)

5. **Enhance backend/services/audio.py with logging**
   - Depends on: logging config (optional but recommended)

6. **Add logging to backend/services/video_rendering.py**
   - Depends on: logging config (optional but recommended)

7. **Enhance tests/test_audio.py** — Audio feature assertion improvements
   - Depends on: requirements.txt (librosa, essentia installed)

8. **Verify tests/test_video_rendering.py** — No code changes; CI must have FFmpeg
   - Depends on: .github/workflows/ci.yml installs FFmpeg

9. **Add E2E test variant to tests/test_api_v1.py**
   - Depends on: requirements.txt (librosa, essentia installed)

10. **Run coverage baseline and update pytest.ini + README**
    - Depends on: All test enhancements complete

11. **Document Phase 2 limitations in README**
    - Depends on: All above complete

---

## 12. VERIFICATION CHECKLIST

After all items are complete, verify:

- [ ] `pip install -r requirements.txt` succeeds
- [ ] CI workflow triggers on push to main/develop and all PRs
- [ ] `pytest tests -q --cov=backend --cov-report=term-missing` shows coverage >= 70%
- [ ] `pytest tests/test_audio.py -v` passes; librosa/essentia assertions conditional on availability
- [ ] `pytest tests/test_video_rendering.py -v` does not skip (FFmpeg installed in CI)
- [ ] `pytest tests/test_api_v1.py::test_v1_e2e_with_real_audio_features -v` passes
- [ ] Log output contains "Job started", "Job stage transition", "Job completed", "Audio verification completed", "Feature extraction completed", "Video render started" with correct fields
- [ ] README documents coverage baseline, logging config, and Phase 2 limitations
- [ ] No new database tables created; v1_* schema unchanged
- [ ] All consent/rights enforcement still intact (no security regression)
- [ ] No real OpenRouter, YouTube, Instagram calls in test runs

---

## Summary of Changed Files

| File | Change | Type |
|------|--------|------|
| `requirements.txt` | Add pytest, pytest-cov, librosa, essentia, python-json-logger | Enhancement |
| `.github/workflows/ci.yml` | New CI workflow with backend-test, frontend-test | New |
| `backend/config.py` | Add logging configuration dict and dictConfig() call | Enhancement |
| `backend/services/job_runner.py` | Add structured logging for job lifecycle | Enhancement |
| `backend/services/audio.py` | Add structured logging for verify/extract | Enhancement |
| `backend/services/video_rendering.py` | Add logging module, logger instance, render logs | Enhancement |
| `tests/test_audio.py` | Upgrade WAV to 2s 44.1k stereo, add librosa/essentia assertions | Enhancement |
| `tests/test_api_v1.py` | Add test_v1_e2e_with_real_audio_features variant | New Test |
| `pytest.ini` | Add markers and strict-markers flag | Enhancement |
| `README.md` | Add Coverage Baseline section, Known Limitations section | Enhancement |

**Total scope:** ~10 files modified/created, 0 database changes, 0 architecture changes, 0 security control weakening.

