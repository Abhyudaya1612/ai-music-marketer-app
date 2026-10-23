# Phase 5-8 Test Fixes - Semantic Review

**Phase 5-8 test suite: 87 passed, 0 failed, 7 skipped.**

This review covers fixes to 14 previously-failing tests across the Phase 5-8 test suite. The root causes were database isolation violations (UNIQUE constraint conflicts when tests run sequentially against shared persistent SQLite files), missing authentication configuration in API endpoint tests, and insufficient per-test cleanup of platform connection records. No changes to business logic or core application behavior; all fixes are test infrastructure and setup/teardown improvements.

Watch for: No blocking concerns. All Phase 5-8 target tests passing; no Phase 1-4 regressions; database schema integration confirmed; job state machine working correctly. Ready to ship.

**Verdict**: APPROVED

---

## High-level view

Database reuse across test functions in persistent SQLite files required per-test cleanup and unique identifiers. The scheduler tests now generate UUID-based job IDs for each test (`f"job-type-{uuid.uuid4()}"` pattern) to prevent UNIQUE constraint violations when tests run sequentially in the same module. The API and e2e publishing tests use a similar strategy: cleaning up related records (songs, profiles, connections, assets) before test execution and using unique owner_ids per test function to ensure test data doesn't bleed across runs.

Authentication configuration is now applied before TestClient creation in `test_e2e_publishing_workflow.py`. The test fixture accepts a `monkeypatch` parameter and sets `settings.api_token` and `settings.auth_user_id` directly, allowing bearer token authentication to pass validation. Individual test methods that need different owner_ids set that attribute before making API calls.

Platform connection tests use an autouse fixture (`cleanup_platform_connections_db()`) that runs before every test, clearing all ConsentRecord, PlatformOAuthState, and PlatformConnection records. This eliminates test state pollution where one test's created connections or consent records would interfere with the next test's assertions.

The Ollama provider test (`test_fallback_includes_song_info`) was failing due to database isolation issues in other test modules; no code changes were needed. The fallback metadata generation already includes artist_name and song_title as expected.

---

<details>
<summary>Issues (0)</summary>

No blocking concerns. All Phase 5-8 tests passing, no regressions, database schema integrated, job state machine operational.

</details>

<details>
<summary>Details</summary>

### Database isolation via UUIDs and per-test cleanup

Job scheduler tests were failing with "UNIQUE constraint violations" because all four test functions created jobs with hardcoded IDs against a shared persistent SQLite database file. The fix uses `uuid.uuid4()` to generate unique job IDs for each test (`f"job-type-{uuid.uuid4()}"`), embedding uniqueness in the ID itself rather than relying on test isolation.

The API v1 onboarding test was leaving artist profiles and songs in the database after execution, causing the `profile GET` to return an existing profile on the next test run instead of None. The fix adds cleanup before the test runs to delete profiles and songs for the test owner, allowing subsequent runs to verify the onboarding flow correctly.

### Authentication configuration and TestClient setup

E2E publishing tests were failing with 401 Unauthorized on all API calls because TestClient was created before `settings.api_token` and `settings.auth_user_id` were configured. TestClient caches the app at fixture time, so settings changes after creation don't take effect.

The fix modifies the `client` fixture to accept `monkeypatch` and configure auth settings before TestClient creation. Individual test methods that need different owner_ids set that attribute before making API calls, ensuring bearer token validation passes and endpoint access control is enforced correctly.

### Platform connections fixture autouse cleanup

Platform connection tests were failing with "UNIQUE constraint violations" because one test's created records persisted into the next test against a shared persistent database file. An autouse fixture clears ConsentRecord, PlatformOAuthState, and PlatformConnection records before each test. Combined with unique owner_id values per test function, this eliminates test state pollution.

### E2E publishing workflow test data cleanup

E2E publishing tests create VideoRender and PlatformConnection records and need to avoid UNIQUE constraint violations on storage_key in MediaAsset and on the YouTube provider + owner_id pair. Individual tests clean up related records before execution to prevent residual connections from prior runs from causing errors. Combined with the fixture's auth setup, all six publishing workflow tests pass and run in any order without cross-test pollution.

### Job state machine and failed_retryable transitions

Scheduler tests verify that the job state machine transitions correctly: queued → running, stale running → queued (with incremented attempt count), jobs exceeding max_attempts stop retrying. These assertions pass once database isolation is fixed. The state machine implementation is working as designed.

### Out-of-scope skipped tests

Seven tests are skipped: three in `test_lyric_video_generation.py` and two in `test_video_rendering.py` (video rendering requires ffmpeg, not available in test environment); two additional skipped tests in other modules. These are pre-existing and correctly left untouched.

</details>

---

## File map

<details>
<summary>Changed files (5)</summary>

- **tests/test_job_scheduler.py** — Added `import uuid`; all job IDs now use `f"job-type-{uuid.uuid4()}"` pattern to prevent UNIQUE constraint conflicts in sequential test execution.

- **tests/test_api_v1.py** — Added per-test cleanup in `test_artist_onboarding_and_dashboard_are_private_and_paginated()` that deletes artist profiles and songs for the test owner before test execution.

- **tests/test_e2e_publishing_workflow.py** — Modified `client` fixture to accept `monkeypatch` parameter and configure auth settings before TestClient creation; individual test methods now accept `monkeypatch` and set owner_id as needed; added per-test cleanup for MediaAsset and PlatformConnection records.

- **tests/test_platform_connections.py** — Added autouse fixture `cleanup_platform_connections_db()` that clears ConsentRecord, PlatformOAuthState, and PlatformConnection records before each test; test functions updated to use unique owner_id values per test.

- **tests/test_ollama_provider.py** — No changes; test was failing due to database isolation issues in other modules, now passes when those are fixed.

</details>

Full diff: `git diff` against base branch (no uncommitted changes to report at this review).

---

**Summary**: Phase 5-8 test failures resolved via database isolation improvements (UUID-based unique IDs, per-test cleanup, autouse fixtures), auth configuration fixes (settings applied before TestClient creation), and cleanup of platform connection test state. All 14 target tests passing, no Phase 1-4 regressions, database schema fully integrated, job state machine operational. Ready to proceed.
