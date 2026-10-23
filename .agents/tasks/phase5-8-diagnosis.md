# Phase 5-8 Test Failure Diagnosis

**Test Results:** 13 failed, 74 passed, 7 skipped (out of 94 total)  
**Run Date:** 2026-10-22

## Summary of Root Causes

The 13 failing tests fall into five distinct root-cause categories:

1. **Test Database Isolation Issues** (1 test) - Database pollution between test functions
2. **Platform Connections Fixture & Consent Flow** (3 tests) - Missing mocking and data isolation
3. **Job Scheduler UNIQUE Constraint Violations** (4 tests) - Test data reuse with shared database
4. **Missing Auth Dependency Mock** (2 tests) - Mock target path incorrect
5. **Ollama Metadata Assertion** (1 test) - Test assertion checking wrong field
6. **Profile Response Serialization** (1 test) - Response body handling for None values

---

## Detailed Failure Analysis

### Category 1: Test Database Isolation

**Failure Summary:**
- `test_artist_onboarding_and_dashboard_are_private_and_paginated` 
  - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_api_v1.py`
  - Error: `AssertionError: assert {'display_name': 'Nova Echo', ...} is None`
  - Root Cause: The test calls `client.get("/api/v1/artist/profile")` which returns 200 with the profile object, but the test setup expects `None` on first access

**Root Cause Analysis:**
- The test database (`test_api_v1.db`) is created once per module and reused across all tests in `test_api_v1.py`
- Previous tests in the same module create an artist profile for the same owner
- The fixture does not clean up between tests
- When this test runs, the profile already exists, so the GET returns the profile instead of None

**Files to Modify:**
- `tests/test_api_v1.py` - Add database cleanup in fixture or test setup

**Fix Required:**
Add a per-test database isolation strategy or clean up profile records between tests.

---

### Category 2: Platform Connections Fixture & Consent Flow (3 tests)

**Failures:**
1. `test_platform_connection_requires_consent_and_requests_read_only_scopes`
   - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_platform_connections.py`
   - Error: `assert 200 == 403`
   - Root Cause: OAuth start endpoint returns 200 when it should return 403 (missing consent requirement)

2. `test_oauth_callback_encrypts_tokens_and_is_one_time_owner_scoped`
   - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_platform_connections.py`
   - Error: `AssertionError: {"error":{"code":"CONSENT_ALREADY_ACTIVE","message":"This consent is already active..."}}`
   - Root Cause: Consent record already exists from previous test run, fixture doesn't clean up

3. `test_withdrawing_connection_consent_deletes_tokens_and_pending_state`
   - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_platform_connections.py`
   - Error: `sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when exactly one was required`
   - Root Cause: Database contains stale platform connections and consent records from earlier tests, query returns multiple results

**Root Cause Analysis:**
- All three tests in `test_platform_connections.py` share the same temporary database file
- Tests create platform connections and consent records that persist across test functions
- Database cleanup between tests is missing
- When withdrawal test queries for connections, it finds duplicates

**Files to Modify:**
- `tests/test_platform_connections.py` - Add database isolation fixtures

**Fix Required:**
1. Create a fresh database or clean relevant tables between tests
2. Ensure previous consent records are cleaned up before test execution
3. Implement fixture to delete stale platform connections

---

### Category 3: Job Scheduler UNIQUE Constraint Violations (4 tests)

**Failures:**
1. `test_scheduler_dispatches_queued_jobs`
2. `test_scheduler_detects_stale_jobs`
3. `test_scheduler_respects_max_attempts`
4. `test_scheduler_atomic_job_dispatch_prevents_duplicates`

All in: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_job_scheduler.py`

**Error:** `sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: v1_jobs.id`

**Root Cause Analysis:**
- All four tests create jobs with hardcoded IDs (e.g., `'test-job-id'`, `'stale-job-id'`, `'max-attempt-job-id'`, `'atomic-job-id'`)
- Tests run sequentially against the same persistent database file (`_scheduler.db`)
- When a second test runs, it tries to insert the same job ID, violating the primary key constraint
- Database is not cleaned between tests

**Files to Modify:**
- `tests/test_job_scheduler.py` - Add per-test database isolation or use unique job IDs

**Fix Required:**
1. Either clean the `v1_jobs` table between test functions
2. Or generate unique job IDs per test instead of using hardcoded values

---

### Category 4: Missing Auth Dependency Mock (2 tests)

**Failures:**
1. `test_publish_requires_succeeded_render`
2. `test_publish_requires_youtube_connection`

Both in: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_e2e_publishing_workflow.py`

**Error:** `AttributeError: <module 'backend.core.auth'...> does not have the attribute 'get_current_owner'`

**Root Cause Analysis:**
- The tests patch `backend.core.auth.get_current_owner`, but the actual function name is `current_owner`
- Patch target does not exist, so the mock fails to apply
- Dependency injection then calls the real `current_owner`, which raises auth error

**Files to Modify:**
- `tests/test_e2e_publishing_workflow.py` - Correct the patch target name

**Fix Required:**
Change all occurrences of `patch("backend.core.auth.get_current_owner")` to `patch("backend.core.auth.current_owner")`

---

### Category 5: Platform Connections UNIQUE Constraint Duplicates (2 tests)

**Failures:**
1. `test_queue_youtube_publish_job`
   - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_e2e_publishing_workflow.py`
   - Error: `sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: v1_platform_connections.owner_id, v1_platform_connections.provider`

2. `test_workflow_metadata_to_youtube`
   - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_e2e_publishing_workflow.py`
   - Error: `sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: v1_platform_connections.owner_id, v1_platform_connections.provider`

**Root Cause Analysis:**
- Both tests create a PlatformConnection for the same owner_id (`test_owner_e2e`) and provider (`youtube`)
- The schema has a unique constraint: `(owner_id, provider)` (line 252 in models.py)
- When the second test runs, it tries to insert a duplicate connection, violating the constraint
- Database is not cleaned between tests

**Files to Modify:**
- `tests/test_e2e_publishing_workflow.py` - Add database isolation

**Fix Required:**
1. Clean or isolate database between tests
2. Delete existing platform connections for the test owner before each test

---

### Category 6: Media Assets UNIQUE Constraint (1 test)

**Failure:**
- `test_queue_lyric_video_render_job`
  - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_e2e_publishing_workflow.py`
  - Error: `sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: v1_media_assets.storage_key`

**Root Cause Analysis:**
- The test creates a MediaAsset with `storage_key="test_key"` 
- Multiple tests in the same file create media assets with the same storage_key
- The schema has `storage_key` as a unique column (line 102 in models.py)
- Database reuse causes constraint violation on second test execution

**Files to Modify:**
- `tests/test_e2e_publishing_workflow.py` - Add database isolation or unique storage keys

**Fix Required:**
1. Clean database between tests, or
2. Generate unique storage keys per test

---

### Category 7: Ollama Metadata Assertion (1 test)

**Failure:**
- `test_fallback_includes_song_info`
  - File: `c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app\tests\test_ollama_provider.py`
  - Error: `assert ('My Artist' in 'My Track' or 'My Artist' in "The lyrics and melody...")`
  - Root Cause: Artist name not included in fallback metadata

**Root Cause Analysis:**
- Test expects artist name to appear in either title or description of fallback metadata
- Actual response: title = `'My Track'`, description does not contain artist
- The fallback metadata generation is missing artist information

**Files to Modify:**
- `backend/services/ollama_provider.py` - Add artist info to fallback metadata
- Or `tests/test_ollama_provider.py` - If this is expected behavior, update the test

**Fix Required:**
Include the artist_name in the fallback metadata generation logic.

---

## Fix Plan (Ordered by Priority)

### Phase 1: Quick Wins (Database Isolation)

**Priority 1.1:** Fix test database cleanup in shared database tests
- Apply to all test files using shared database files
- Affects: 11 tests across 3 test files
- Effort: Low
- Impact: High

**Priority 1.2:** Fix mock target paths
- Change `backend.core.auth.get_current_owner` → `backend.core.auth.current_owner`
- Affects: 2 tests
- Effort: Very Low
- Impact: High

### Phase 2: Assertion & Logic Fixes

**Priority 2.1:** Add artist name to Ollama fallback metadata
- Update fallback generation to include artist
- Affects: 1 test
- Effort: Low
- Impact: Medium

**Priority 2.2:** Address profile endpoint response handling
- Ensure profile GET returns correct None vs object behavior
- Affects: 1 test
- Effort: Medium
- Impact: Low (may require design clarification)

---

## Implementation Steps

1. **Isolate databases in test_api_v1.py:**
   - Add conftest fixture to create fresh database per test function
   - Or add setup/teardown to delete artist profiles between tests

2. **Isolate databases in test_platform_connections.py:**
   - Add conftest fixture or per-test cleanup
   - Delete consent records and platform connections before each test

3. **Isolate databases in test_e2e_publishing_workflow.py:**
   - Add conftest fixture
   - Generate unique IDs for each test run (use UUID or timestamps)
   - Delete test data (songs, assets, renders, connections) between tests

4. **Fix auth mock paths in test_e2e_publishing_workflow.py:**
   - Replace all `patch("backend.core.auth.get_current_owner")` with `patch("backend.core.auth.current_owner")`

5. **Fix scheduler test job IDs in test_job_scheduler.py:**
   - Use unique job IDs per test (e.g., prepend test function name or timestamp)
   - Or add database cleanup before each test

6. **Update Ollama fallback metadata in backend/services/ollama_provider.py:**
   - Include artist_name in the fallback metadata response

---

## Verification Commands

After each fix, run:
```powershell
cd c:\Users\mohak\OneDrive\Desktop\ai-music-marketer-app
.\.venv_new\Scripts\Activate.ps1
python -m pytest tests/ -v --tb=short
```

Expected result: 85+ passed, 0 failed, 7 skipped
