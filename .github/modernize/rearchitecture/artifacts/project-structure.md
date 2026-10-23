# Project Structure and Rewrite Boundary

## Delivered target structure

- **Project type:** Local-first modular monolith with a Next.js App Router frontend and FastAPI API service.
- **Frontend:** `frontend/app/` contains the Next.js interface; `frontend/lib/` contains its API client and typed response contracts.
- **Backend:** Existing routes and ORM models remain available for legacy clients. The new `/api/v1` routes use `backend/domain/`, `backend/core/`, `backend/services/`, and durable SQLAlchemy job/analysis and platform-connection records; `backend/routers/connections.py` owns the read-only OAuth flows.
- **First-slice worker:** `backend/services/job_runner.py` verifies uploaded audio and persists analysis/report outcomes; `backend/workers.py` retains the legacy route pipeline, which is also exposed on demand from the v1 dashboard after analysis.
- **Private media:** Original uploads, derived audio, and completed video MP4s are stored outside the public frontend tree under `APP_MEDIA_STORAGE_PATH`.
- **Video rendering:** The v1 song API records consent-gated video-render requests; the versioned worker renders the two approved formats locally through FFmpeg and persists private output plus provenance/validation metadata.
- **Verification and packaging:** `tests/` covers legacy behavior, v1 API flow, and audio decoding; `scripts/package_demo.ps1` creates a source ZIP without local data or dependencies.
- **Runtime:** Run the Next.js frontend on port 3000 and FastAPI on port 8000. Docker Compose starts both services.
- **Data:** `music_marketer.db` remains the existing SQLite database; new `v1_*` tables are created without destructive migration.

## Preserved source behavior

- Legacy `/api/*` routes and their database models are retained. The deterministic five-agent pipeline is available through those compatibility routes and through authenticated, consent-gated `/api/v1/analyses/{analysis_id}/agent-pipeline` routes.
- Campaign, profile, calendar, and simulated analytics functionality are legacy behavior, not part of the new private audio-analysis milestone.
- The old static frontend has been replaced by the approved Next.js interface.

## Existing request flows

- Legacy song creation persists the legacy record and schedules the original pipeline through FastAPI `BackgroundTasks`.
- The worker creates a run, runs the deterministic five-agent pipeline, stores its output in related tables, and updates song/run status.
- The new v1 flow writes the private upload, validates it through FFprobe, creates a versioned analysis and durable job, then stores Song Intelligence and a schema-validated A&R report.
- The dashboard can run the five-agent pipeline against a completed v1 analysis. It uses saved song metadata and structured audio estimates plus only derived lyric candidates; its latest output is stored in `v1_agent_pipeline_runs`. Audience matching is generic and heuristic, and campaign metrics are simulated.
- The later video-render flow creates an owner-scoped render and idempotency record, queues the in-process worker, rechecks rights and scoped processing/promotional consent, and stores a validated private MP4 with source provenance.
- Read-only social account linking uses owner-scoped consent and hashed one-time OAuth state; provider codes are exchanged server-side, tokens are Fernet-encrypted in SQLite, and only token-free connection status is returned to the frontend.
- Campaign, profile, calendar, and dashboard requests synchronously read/write the same SQLAlchemy database.

## Scope interpretation

The requested target is a new modular-monolith structure with Next.js frontend and FastAPI backend, while keeping the existing REST paths and response behavior available for legacy clients. The supplied specifications' initial acceptance boundary is the private audio upload → analysis job → versioned intelligence → A&R report flow. The existing campaign planner and simulated analytics are legacy behavior, not authorization to expand the new milestone.
