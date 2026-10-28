# Tests

Pytest suite covering the backend API, engine, and services, plus end-to-end workflows.

## Running

```powershell
.\.venv\Scripts\python.exe -m pytest
# or a single file
.\.venv\Scripts\python.exe -m pytest tests/test_api_v1.py -v
```

Configuration lives in [`../pytest.ini`](../pytest.ini): `testpaths = tests`, `--strict-markers -v`,
with `unit`, `integration` and `slow` markers.

## Fixtures

[`conftest.py`](conftest.py) provides an in-memory SQLite `db` session fixture
(`Base.metadata.create_all`) used by the API and service tests.

## Coverage areas

- API surface: `test_api.py`, `test_api_v1.py`, `test_campaigns.py`, `test_video_api.py`
- Engine and services: `test_engine.py`, `test_audio.py`, `test_lyrics.py`,
  `test_audience.py`, `test_release_planning.py`
- Video and lyrics rendering: `test_lyric_video_generation.py`,
  `test_lyrics_rendering.py`, `test_video_rendering.py`, `test_genre_visualizers.py`
- Publishing and platform connections: `test_youtube_publisher.py`,
  `test_platform_connections.py`, `test_job_runner_publishing.py`
- Jobs and scheduling: `test_job_scheduler.py`
- End-to-end: `test_e2e_workflow.py`, `test_e2e_publishing_workflow.py`
