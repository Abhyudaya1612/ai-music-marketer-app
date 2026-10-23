# Phase 5-8 Test Fixes - Verification Report

**Date:** 2026-10-22  
**Verification Run:** Final

## Test Results

```
87 passed, 7 skipped, 0 failed
```

**Change from Start:** +14 passed (from 73 to 87 passed), 0 failed (from 14 to 0 failed)

---

## Fixes Applied

### Category A: Database Isolation Issues

**Fixed:** All 4 tests in `test_job_scheduler.py`
- `test_scheduler_dispatches_queued_jobs` ✓
- `test_scheduler_detects_stale_jobs` ✓
- `test_scheduler_respects_max_attempts` ✓
- `test_scheduler_atomic_job_dispatch_prevents_duplicates` ✓

**Solution:** Added UUID-based unique job IDs using `uuid.uuid4()` to prevent UNIQUE constraint violations when tests run sequentially against the same persistent database file.

**Fixed:** 1 test in `test_api_v1.py`
- `test_artist_onboarding_and_dashboard_are_private_and_paginated` ✓

**Solution:** Added per-test database cleanup that deletes artist profiles and songs for the test owner before test execution, ensuring the profile GET returns None as expected on first access.

### Category B: Platform Connections Fixture & Database Isolation

**Fixed:** All 3 tests in `test_platform_connections.py`
- `test_platform_connection_requires_consent_and_requests_read_only_scopes` ✓
- `test_oauth_callback_encrypts_tokens_and_is_one_time_owner_scoped` ✓
- `test_withdrawing_connection_consent_deletes_tokens_and_pending_state` ✓

**Solution:** 
1. Added autouse fixture `cleanup_platform_connections_db()` that runs before each test, clearing all ConsentRecord, PlatformOAuthState, and PlatformConnection records from the database.
2. Used unique owner_id values per test (e.g., "platform-owner-consent-unique") to isolate test data.

### Category C: End-to-End Publishing Workflow

**Fixed:** All 6 tests in `test_e2e_publishing_workflow.py`
- `test_capabilities_includes_publishing_flags` ✓ (already passing)
- `test_queue_lyric_video_render_job` ✓
- `test_queue_youtube_publish_job` ✓
- `test_publish_requires_succeeded_render` ✓
- `test_publish_requires_youtube_connection` ✓
- `test_workflow_metadata_to_youtube` ✓

**Solutions Applied:**
1. **Authentication Setup:** Updated the `client` fixture to accept `monkeypatch` parameter and set `settings.api_token` and `settings.auth_user_id` before creating the TestClient, enabling bearer token authentication to work properly.
2. **Database Isolation:** Added per-test cleanup to delete existing PlatformConnection records for YouTube to prevent UNIQUE constraint violations across sequential tests.
3. **Unique Storage Keys:** Added cleanup for MediaAsset records with duplicate storage_keys to avoid constraint violations in render tests.
4. **Owner ID Management:** Each test method accepts `monkeypatch` parameter and sets `settings.auth_user_id` to match the test_owner fixture, ensuring auth checks pass correctly.

### Category D: Ollama Provider

**Fixed:** 1 test in `test_ollama_provider.py`
- `test_fallback_includes_song_info` ✓

**Note:** No code changes needed. The fallback metadata generation in `_fallback_metadata()` already includes artist_name in both the title and description, satisfying the test assertion. The test was failing due to database isolation issues in other test files that have now been resolved.

---

## Root Causes Resolved

1. **Database Reuse Without Cleanup:** Tests sharing persistent SQLite database files (_scheduler.db, _e2e_pub.db, _platform.db, _v1.db) with hardcoded or non-unique IDs led to UNIQUE constraint violations when tests ran sequentially.

2. **Missing Authentication Configuration:** The TestClient in `test_e2e_publishing_workflow.py` was not configured with valid `api_token` in settings, causing all endpoint calls to fail with 401 Unauthorized.

3. **Insufficient Database Isolation:** Platform connection tests lacked per-test cleanup of consent and OAuth state records, causing test state pollution across test functions.

4. **Test Data Pollution Across Modules:** The single persistent database file per test module meant that previous test runs in the same module left data behind, affecting subsequent test execution.

---

## Implementation Details

### Key Changes

1. **test_job_scheduler.py:** Added `import uuid` and modified all hardcoded job IDs to use `f"job-type-{uuid.uuid4()}"` pattern.

2. **test_api_v1.py:** 
   - Added import: `from backend.database import SessionLocal`
   - Added database cleanup in test using ArtistWorkspaceProfile and StudioSong models

3. **test_e2e_publishing_workflow.py:**
   - Added import: `from backend.config import settings`
   - Updated `client` fixture to configure auth settings before TestClient creation
   - Added `monkeypatch` parameter to test methods that need different owner_ids
   - Added database cleanup to remove duplicate PlatformConnection and MediaAsset records

4. **test_platform_connections.py:**
   - Added import: `from backend.domain.models import ConsentRecord`
   - Added autouse fixture `cleanup_platform_connections_db()` with function scope
   - Updated all tests to use unique owner_id values

---

## Tests Still Skipped (7 total)

These are unrelated to Phase 5-8 work and are documented out-of-scope:
- `test_lyric_video_generation.py`: 3 skipped (video rendering tests require ffmpeg, external dependency)
- `test_video_rendering.py`: 2 skipped (same reason)
- (2 additional skipped tests in other modules)

All 7 skipped tests are pre-existing and not related to Phase 5-8 scope.

---

## Verification Checklist

- [x] All 14 previously failing tests now pass
- [x] No regressions in existing passing tests (87 total passed)
- [x] Database isolation properly implemented across all affected test files
- [x] Authentication configuration properly set up for API endpoint tests
- [x] Unique IDs prevent constraint violations in sequential test execution
- [x] Test data cleanup runs automatically via autouse fixtures and per-test setup

