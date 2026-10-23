"""API integration tests — run after `pip install -r requirements.txt`.

    pytest tests/ -v
Uses an isolated SQLite DB via APP_DATABASE_URL env override.
"""
import os, tempfile
os.environ["APP_DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from backend.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_full_flow():
    r = client.post("/api/songs", json={
        "title": "Test Track", "artist": "Tester", "genre": "rock",
        "lyrics": "We rise, we fall, we rise again"})
    assert r.status_code == 201
    song_id = r.json()["id"]

    import time
    for _ in range(50):
        detail = client.get(f"/api/songs/{song_id}").json()
        if detail["status"] != "analyzing":
            break
        time.sleep(0.2)

    assert detail["status"] == "complete"
    run = detail["runs"][0]
    assert run["intelligence"]["bpm"] > 0
    assert len(run["segments"]) == 5
    assert len(run["content_pieces"]) == 5
    assert run["metrics"]["score"] > 0
    assert "STAGE 5" in "".join(run["logs"])


def test_stats():
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["total_songs"] >= 1
