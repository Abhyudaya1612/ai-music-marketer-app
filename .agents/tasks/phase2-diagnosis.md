# Phase 2 Diagnosis: Background Job Execution Problem

## Exact v1_jobs Table Schema

**Table:** `v1_jobs` (via AnalysisJob model in models.py)

**Relevant columns:**
- `id` (String[36], PK): Job ID
- `owner_id` (String[120], indexed): Owner scoping
- `task_type` (String[40]): One of "asset_verification", "song_analysis", "video_render"
- `subject_id` (String[36], indexed): Asset ID (for verification), Analysis ID (for analysis), VideoRender ID (for rendering)
- `status` (String[24], indexed): One of "queued", "running", "succeeded", "failed"
- `stage` (String[48]): Sub-status tracking (e.g., "starting", "audio_processing", "validating_features", "generating_report", "completed", "failed")
- `attempt` (Integer): Defaults to 1; no retry logic implemented
- `error_code` (String[80]): Filled when status="failed"
- `created_at` (DateTime, UTC): Job creation timestamp
- `updated_at` (DateTime, UTC): Last update timestamp
- `started_at` (DateTime, UTC, nullable): When job transitioned to "running"
- `finished_at` (DateTime, UTC, nullable): When job reached terminal state

**Initial status:** "queued" (default in model)

---

## Code Path: POST /analyses → Queued Job

**File:** `backend/routers/v1.py`, function `create_analysis()`

### Steps:

1. **Authorization checks** (lines ~820-850):
   - Validate song exists and owner matches
   - Check `audio_processing`, `derived_analysis_storage` consent
   - Check `third_party_ai` consent if `allow_third_party_ai=True`

2. **Idempotency check** (lines ~851-860):
   - Query `IdempotencyRecord` by (owner_id, operation, key)
   - If found and request_hash matches, return cached response
   - If found and request_hash differs, raise 409 IDEMPOTENCY_CONFLICT

3. **Duplicate analysis check** (lines ~862-868):
   - Query `SongAnalysis` by (song_id, asset_id, status in ["queued", "running"])
   - If found, raise 409 ANALYSIS_ALREADY_RUNNING

4. **Create AnalysisJob** (lines ~870-871):
   ```python
   job = AnalysisJob(owner_id=owner_id, task_type="song_analysis")
   db.add(job)
   db.flush()
   ```
   - Status defaults to "queued" (from model default)

5. **Create SongAnalysis** (lines ~872-877):
   ```python
   analysis = SongAnalysis(
       song_id=song_id,
       asset_id=asset.id,
       owner_id=owner_id,
       job_id=job.id,
       analysis_version=payload.analysis_profile,
   )
   db.add(analysis)
   db.flush()
   ```
   - Status defaults to "queued"

6. **Optional: Add SongAnalysisLyrics** (lines ~878-883):
   ```python
   if payload.lyrics and payload.lyrics.strip():
       db.add(SongAnalysisLyrics(...))
   ```

7. **Create IdempotencyRecord** (lines ~890-899):
   ```python
   db.add(IdempotencyRecord(...))
   db.commit()  # <-- ONLY db.commit() in the entire endpoint
   ```

8. **Schedule background task** (lines ~900-906):
   ```python
   background.add_task(
       run_v1_job,
       job.id,
       payload.generate_ai_report,
       payload.allow_third_party_ai,
   )
   ```

### Key Observation:

The job is created with `status="queued"` and immediately added to FastAPI's `BackgroundTasks` queue via `background.add_task(run_v1_job, job.id)`.

---

## Does run_v1_job() Exist? What Does It Do?

**Yes, it exists.** File: `backend/services/job_runner.py`

### Function Signature (line 39):
```python
def run_v1_job(
    job_id: str,
    generate_ai_report: bool = True,
    allow_third_party_ai: bool = False,
) -> None:
```

### Status Transitions:

1. **Fetch job by ID** (line 45):
   ```python
   job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
   if job is None or job.status != "queued":
       return
   ```
   - **CRITICAL:** If job is already running or finished, the function returns immediately (no re-execution)

2. **Transition to "running"** (lines 46-49):
   ```python
   job.status = "running"
   job.stage = "starting"
   job.started_at = _utcnow()
   job.updated_at = job.started_at
   db.commit()
   ```

3. **Process by task_type** (lines 50-59):
   - `"asset_verification"` → `_verify_asset_job(db, job)`
   - `"song_analysis"` → `_analysis_job(db, job, generate_ai_report, allow_third_party_ai)`
   - `"video_render"` → `_video_render_job(db, job)`
   - Otherwise → `_fail_job(db, job, "INTERNAL_ERROR")`

4. **Terminal states:**
   - Success: `job.status = "succeeded"`, `job.stage = "completed"`, `job.finished_at = now`
   - Failure: `job.status = "failed"`, `job.stage = "failed"`, `job.error_code = "..."`
   - All terminal states call `db.commit()`

### Exception Handling:

- Outer `try/except` (lines 60-72): Catches any exception and attempts to persist failure
- Inner rollback + recovery (lines 64-71): If outer exception caught, tries to mark job as failed with `"INTERNAL_ERROR"`
- If recovery fails, logs error and rolls back

---

## Is There Any Scheduler or Worker Loop Calling run_v1_job()?

**No scheduler exists.** File: `backend/main.py`

### Startup/Shutdown Lifecycle:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
```

- **Startup:** Calls `init_db()` to create tables (no worker initialization)
- **Shutdown:** No cleanup (no worker shutdown)

### What Calls run_v1_job()?

Only TWO callers:
1. **FastAPI BackgroundTasks** (endpoint creates job, adds to background queue):
   - `backend/routers/v1.py`, line 906: `background.add_task(run_v1_job, job.id, ...)`
   - `backend/routers/v1.py`, line 728: `background.add_task(run_v1_job, job.id)` (for asset_verification)

2. **Test code** (manual invocation):
   - `tests/test_api_v1.py` uses monkeypatch to replace `verify_audio` and `extract_features` but doesn't manually call `run_v1_job()`
   - The test still uses BackgroundTasks to schedule it
   - Tests run synchronously via `TestClient` which **executes BackgroundTasks immediately within the request context**

### The Root Problem:

FastAPI's `BackgroundTasks` is designed to execute after the response is sent to the client. However, in the current architecture:

- **No explicit background worker process** is running to continuously monitor the database for queued jobs
- **BackgroundTasks works fine in tests** (TestClient executes them immediately)
- **BackgroundTasks might not work reliably in production** (depends on the ASGI server implementation)
- **No retry loop** exists to pick up jobs that were queued but whose BackgroundTasks callback never fired
- **No durability guarantee** — if the API container crashes before BackgroundTasks runs, the job stays queued forever

### Workers.py Does NOT Apply:

`backend/workers.py` contains `execute_pipeline()` which operates on legacy `models.Song`, not `AnalysisJob`. It is **not called anywhere** in the v1 architecture and is vestigial.

---

## Is APScheduler Already in requirements.txt?

**No.** Current `requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pydantic>=2.6
pydantic-settings>=2.2
httpx>=0.27
cryptography>=42.0
pytest>=8.0
pytest-cov>=4.0
librosa>=0.10
anyio>=4.0
```

No APScheduler, no APQueue, no Celery, no RQ.

---

## Does main.py Have Startup/Shutdown Hooks?

**Yes, but minimal.** File: `backend/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # <-- Creates tables only
    yield
```

- **Startup:** `init_db()` → creates SQLAlchemy tables if they don't exist (idempotent)
- **Shutdown:** No code (implicit `yield`)
- **No background scheduler or worker** is started

---

## Minimal Change Needed for Automatic Job Execution

**Problem:** Queued jobs are added to BackgroundTasks but may never execute if:
1. The task callback was lost before it ran
2. The API container crashes during request handling
3. The ASGI server doesn't guarantee BackgroundTasks execution
4. Multiple replicas of the API are running (each only sees its own tasks)

**Solution (smallest, most durable):**

1. **Add a background polling loop in the lifespan startup** (not BackgroundTasks):
   - Start a background asyncio task that polls `AnalysisJob` table every 1-5 seconds
   - Find all jobs with `status="queued"` and `attempt <= max_retries`
   - For each, lock it (`status="running"`) and call `run_v1_job()`
   - If `run_v1_job()` succeeds and commits, the task moves to terminal state and will not be picked again
   - If `run_v1_job()` crashes without persisting, the job remains in "running" and will be considered stale after `idle_timeout_seconds` (default: 60 or 300), then retried

2. **Add two new env vars** (optional, safe defaults):
   - `APP_JOB_WORKER_ENABLED` (default: "true"): Enable/disable background worker
   - `APP_JOB_POLL_INTERVAL_SECONDS` (default: "5"): Poll frequency
   - `APP_JOB_IDLE_TIMEOUT_SECONDS` (default: "300"): How long "running" = stuck before retry
   - `APP_JOB_MAX_ATTEMPTS` (default: "3"): Max retries per job

3. **Modify AnalysisJob schema** (optional):
   - Consider adding a `last_attempted_at` timestamp to detect stale "running" jobs

4. **Keep BackgroundTasks** (unchanged):
   - The endpoint still adds tasks to BackgroundTasks; if they execute before the job is picked up by the poller, the poller will skip it (already succeeded or already running)
   - This gives us best-of-both: fast execution when it works, durability when it doesn't

---

## Existing Retry or Idempotency Mechanisms?

### Retry:
- **Not implemented.** `AnalysisJob.attempt` is initialized to 1 but never incremented
- No built-in retry loop (only the proposed polling loop will add this)
- If a job fails, it stays failed indefinitely

### Idempotency:
- **Partially implemented** for analysis job *submission* (not execution):
  - `IdempotencyRecord` table stores one (owner_id, operation, key) tuple per analysis request
  - If you submit the same request twice with the same Idempotency-Key, you get the same AnalysisJob and Analysis IDs
  - However, if both jobs somehow execute (e.g., manual intervention + BackgroundTasks), both will run the analysis independently
- **No mechanism** to prevent duplicate *execution* of the same job

### Safeguards Needed:
1. Lock job to "running" before attempting execution (prevents concurrent re-execution)
2. Increment `attempt` and check against `max_attempts` before retry
3. Respect consent and authorization checks on every execution (already done in `_analysis_job()`)

---

## Summary: Root Cause & Minimal Fix

### Root Cause:
FastAPI's `BackgroundTasks` is not durable. Queued jobs depend on it but have no fallback. In production, if the request completes before the task runs, or if the container crashes, the job is lost.

### Minimal Change:
Add a background poller task in the lifespan that:
1. Queries for `status="queued"` jobs every N seconds
2. Transitions each to `"running"` and calls `run_v1_job()`
3. Handles stale "running" jobs (older than `idle_timeout`) by retrying up to `max_attempts`

### Why This Approach:
- **Smallest code change:** ~50 lines in main.py
- **Preserves existing architecture:** No new queue system, no new process
- **Durable:** Jobs are durably stored in database; poller always finds them
- **Testable:** Can mock the database to test polling logic
- **Safe:** Existing BackgroundTasks optimization is kept; poller only runs what it finds
- **No breaking changes:** Existing auth, consent, rights checks remain intact

---

## Files to Modify for Phase 2 Fix

1. **backend/main.py** (~50 lines):
   - Import `asyncio`, add async background worker coroutine
   - Add to lifespan startup, cancel on shutdown

2. **backend/config.py** (~5 lines):
   - Add job worker env vars (optional; can use hardcoded defaults)

3. **tests/test_api_v1.py** (~20 lines):
   - Ensure existing test still passes (BackgroundTasks compatibility)
   - Add new test: create job, verify it is queued, check poller picks it up

4. **No changes needed** to:
   - models.py (schema is already correct)
   - services/job_runner.py (logic is correct)
   - routers/v1.py (endpoints are correct)
   - database.py (OK as-is)
