# Existing Technology Stack

## Delivered target additions

- **Frontend:** Next.js 15 App Router, React 19, TypeScript, Tailwind CSS 4, and Lucide icons; served separately on port 3000.
- **Versioned API and private media:** FastAPI `/api/v1`, bearer-protected single-workspace access, private local file storage, FFmpeg/FFprobe validation, SQLAlchemy `v1_*` tables, and owner-scoped asynchronous jobs.
- **Video rendering:** Local FFmpeg/FFprobe capability-gated motion graphics (waveform visualizer and spectrum-based full-video format), H.264/AAC MP4 output, owner-scoped render records, asynchronous progress, scoped consent rechecks, and private downloads. No paid video API, artwork upload, local generative-video model, or publishing integration is active.
- **Social account connections:** Provider OAuth 2.0 for YouTube, Instagram professional accounts, and Facebook public profiles using least-privilege read-only scopes, one-time state, server-side token exchange, and Fernet-encrypted SQLite tokens. Requires provider app credentials and `APP_TOKEN_ENCRYPTION_KEY`; no publishing or Facebook Page permissions are requested.
- **Artist workspace and governance:** Owner-scoped v1 profile onboarding/editing and cursor-paginated song dashboard; per-song rights declarations; append-only consent grant/withdrawal records; and separate processing/third-party AI consent gates, using the existing single-workspace bearer identity. This is not multi-user account authentication.
- **Report generation:** Offline mock provider by default; optional server-side OpenRouter adapter with bounded retries, typed output validation, and evidence-reference checks.
- **Local sharing:** Docker Compose starts separate frontend/backend services; `scripts/package_demo.ps1` creates a source ZIP without local data, secrets, or dependencies.
- **Deferred decisions:** SQLite-to-PostgreSQL migration, external queue, and cloud object storage remain unapproved and have not been silently applied.

## Source baseline before the rewrite

- **Language/runtime:** Python source; the project environment observed during analysis is Python 3.14.0.
- **HTTP framework:** FastAPI, declared as `fastapi>=0.110`; the configured environment contains FastAPI 0.143.1 and Uvicorn 0.54.0.
- **Persistence:** SQLAlchemy ORM `>=2.0` (configured environment 2.1.4) and SQLite by default. `APP_DATABASE_URL` can select another SQLAlchemy URL; PostgreSQL driver is commented out in `requirements.txt`.
- **Validation/configuration:** Pydantic `>=2.6`, pydantic-settings `>=2.2`.
- **Frontend:** the original source used plain HTML, CSS, and browser JavaScript; the delivered target frontend is documented above.
- **Async/work:** FastAPI `BackgroundTasks` starts a Python daemon thread for the existing pipeline. No durable external queue is configured.
- **Build/runtime packaging:** Python `requirements.txt`, single-stage `python:3.12-slim` Dockerfile, Docker Compose app service, SQLite volume.
- **Testing:** pytest and FastAPI TestClient; API tests use a temporary SQLite database; agent tests call the deterministic pipeline.
- **Audio/AI integrations:** No FFmpeg, Essentia, Librosa, OpenRouter, or object-storage integration is declared in the existing requirements. Audio feature values and campaign metrics are currently deterministic heuristic/simulation outputs.
- **Configuration:** `APP_ENVIRONMENT`, `APP_DATABASE_URL`, and `APP_CORS_ORIGINS` are read by `backend/config.py`; `.env.example` contains local defaults only.
- **Deprecated/EOL findings:** No explicit deprecation policy or package lockfile was found in the inspected project files. The existing stack does not declare pinned dependency versions.
