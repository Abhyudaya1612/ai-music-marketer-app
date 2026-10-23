from __future__ import annotations

import os
import sys
import tempfile
import json

os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='_v1.db')}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.main import app  # noqa: E402
from backend.database import SessionLocal  # noqa: E402

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-studio-token"}


def test_v1_upload_analysis_and_report_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", "test-artist")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "ai_provider", "mock")

    from backend.services import job_runner

    monkeypatch.setattr(
        job_runner,
        "verify_audio",
        lambda _key: {
            "duration_seconds": 42.5,
            "sample_rate": 44100,
            "channels": 2,
            "actual_content_type": "audio/wav",
        },
    )
    monkeypatch.setattr(
        job_runner,
        "extract_features",
        lambda _key, checksum: {
            "audio_features": {
                "duration_seconds": {
                    "value": 42.5,
                    "status": "measured",
                    "unit": "seconds",
                    "source": "ffprobe",
                    "source_version": "test",
                    "limitations": [],
                },
                "tempo_bpm": {
                    "value": 120.0,
                    "status": "estimated",
                    "unit": "bpm",
                    "source": "librosa",
                    "source_version": "test",
                    "limitations": [],
                },
            },
            "sections": [],
            "hook_candidates": [],
            "lyrics_analysis": {"available": False, "themes": [], "candidate_lines": []},
            "predictions": [],
            "limitations": ["No listening or audience response data was available."],
            "provenance": [{"component": "test", "version": "1", "input_checksum_sha256": checksum}],
        },
    )

    created = client.post("/api/v1/songs", headers=AUTH, json={"title": "Small Hours"})
    assert created.status_code == 201, created.text
    song_id = created.json()["song_id"]
    processing_consent = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "audio_processing", "song_id": song_id},
    )
    assert processing_consent.status_code == 201, processing_consent.text
    declaration = client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "authorized",
            "rights_confirmed": True,
        },
    )
    assert declaration.status_code == 201, declaration.text

    intent = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json={
            "filename": "..\\demo.wav",
            "declared_content_type": "audio/wav",
            "size_bytes": 12,
            "asset_kind": "audio_original",
        },
    )
    assert intent.status_code == 201, intent.text
    assert "demo.wav" not in intent.json()["upload_url"]
    asset_id = intent.json()["asset_id"]

    uploaded = client.put(
        f"/api/v1/assets/{asset_id}/upload",
        headers=AUTH,
        content=b"not-a-real-wav",
    )
    assert uploaded.status_code == 400
    assert uploaded.json()["error"]["code"] == "UPLOAD_SIZE_MISMATCH"

    uploaded = client.put(
        f"/api/v1/assets/{asset_id}/upload",
        headers=AUTH,
        content=b"123456789012",
    )
    assert uploaded.status_code == 204
    completed = client.post(
        f"/api/v1/songs/{song_id}/assets/complete",
        headers=AUTH,
        json={"asset_id": asset_id},
    )
    assert completed.status_code == 202, completed.text
    assert client.get(completed.json()["status_url"], headers=AUTH).json()["status"] == "succeeded"

    no_analysis_storage_consent = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "analysis-without-storage-consent"},
        json={"asset_id": asset_id},
    )
    assert no_analysis_storage_consent.status_code == 403
    assert no_analysis_storage_consent.json()["error"]["code"] == "CONSENT_REQUIRED"
    analysis_storage_consent = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "derived_analysis_storage", "song_id": song_id},
    )
    assert analysis_storage_consent.status_code == 201

    analysis_request = {
        "asset_id": asset_id,
        "analysis_profile": "standard_v1",
        "include_pretrained_predictions": False,
        "generate_ai_report": True,
        "allow_third_party_ai": True,
        "lyrics": "Neon on the water\nI miss the city\nNeon on the water",
    }
    denied_external_ai = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "analysis-without-third-party-consent"},
        json=analysis_request,
    )
    assert denied_external_ai.status_code == 403
    assert denied_external_ai.json()["error"]["code"] == "CONSENT_REQUIRED"
    third_party_consent = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "third_party_ai", "song_id": song_id},
    )
    assert third_party_consent.status_code == 201, third_party_consent.text
    accepted = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "analysis-test-key"},
        json=analysis_request,
    )
    assert accepted.status_code == 202, accepted.text
    analysis_id = accepted.json()["analysis_id"]
    assert client.get(accepted.json()["status_url"], headers=AUTH).json()["status"] == "succeeded"

    replay = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "analysis-test-key"},
        json=analysis_request,
    )
    assert replay.status_code == 202
    assert replay.json()["analysis_id"] == analysis_id
    changed = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "analysis-test-key"},
        json={**analysis_request, "generate_ai_report": False},
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    intelligence = client.get(f"/api/v1/analyses/{analysis_id}/intelligence", headers=AUTH)
    assert intelligence.status_code == 200
    assert intelligence.json()["audio_features"]["duration_seconds"]["status"] == "measured"
    assert intelligence.json()["lyrics_analysis"]["themes"] == ["nightlife and escape", "loss and longing"]
    assert intelligence.json()["lyrics_analysis"]["candidate_lines"][0]["text"] == "Neon on the water"
    assert intelligence.json()["hook_candidates"][0]["kind"] == "lyrical"
    assert intelligence.json()["schema_version"] == "1.1"
    from backend.database import SessionLocal
    from backend.domain.models import SongAnalysisLyrics

    with SessionLocal() as db:
        lyrics_record = db.query(SongAnalysisLyrics).filter_by(analysis_id=analysis_id).one()
        assert "Neon on the water" in json.dumps(lyrics_record.analysis_json)
        assert "I miss the city" not in json.dumps(lyrics_record.analysis_json)
    audience = client.get(
        f"/api/v1/analyses/{analysis_id}/audience-hypotheses",
        headers=AUTH,
    )
    assert audience.status_code == 200, audience.text
    assert audience.json()["hypotheses"][0]["evidence"][0]["source"] == "lyrics_analysis.themes"
    assert "demographic" in audience.json()["hypotheses"][0]["uncertainty"]
    monkeypatch.setattr(settings, "auth_user_id", "different-artist")
    hidden_audience = client.get(
        f"/api/v1/analyses/{analysis_id}/audience-hypotheses",
        headers=AUTH,
    )
    assert hidden_audience.status_code == 404
    monkeypatch.setattr(settings, "auth_user_id", "test-artist")
    report = client.get(f"/api/v1/analyses/{analysis_id}/report", headers=AUTH)
    assert report.status_code == 200
    assert report.json()["provider"] == "mock"
    assert all(
        reference in {
            f"audio_features.{key}" for key, value in intelligence.json()["audio_features"].items()
            if value["value"] is not None
        }
        for section in ("strengths", "improvement_opportunities", "hook_candidates", "recommendations")
        for claim in report.json()[section]
        for reference in claim["evidence_refs"]
    )
    assert client.get(
        f"/api/v1/analyses/{analysis_id}/agent-pipeline",
        headers=AUTH,
    ).json() is None
    agent_pipeline = client.post(
        f"/api/v1/analyses/{analysis_id}/agent-pipeline",
        headers=AUTH,
    )
    assert agent_pipeline.status_code == 200, agent_pipeline.text
    pipeline_results = agent_pipeline.json()["results"]
    assert pipeline_results["audience"]["primary_segment"]
    assert len(pipeline_results["content_plan"]["pieces"]) == 5
    assert pipeline_results["marketing_strategy"]["timeline_weeks"] == 6
    assert pipeline_results["optimization"]["metrics"]["streams"] > 0
    pipeline_log = "\n".join(pipeline_results["logs"])
    for agent in (
        "MUSIC_ANALYSIS_AGENT",
        "AUDIENCE_INTELLIGENCE_AGENT",
        "CONTENT_STRATEGY_AGENT",
        "MARKETING_STRATEGY_AGENT",
        "ANALYTICS_OPTIMIZATION_AGENT",
    ):
        assert agent in pipeline_log
    assert any("simulated" in item.lower() for item in agent_pipeline.json()["limitations"])
    assert client.get(
        f"/api/v1/analyses/{analysis_id}/agent-pipeline",
        headers=AUTH,
    ).json() == agent_pipeline.json()
    consent_withdrawal = client.post(
        f"/api/v1/consents/{analysis_storage_consent.json()['consent_id']}/withdraw",
        headers=AUTH,
    )
    assert consent_withdrawal.status_code == 200
    blocked_pipeline = client.post(
        f"/api/v1/analyses/{analysis_id}/agent-pipeline",
        headers=AUTH,
    )
    assert blocked_pipeline.status_code == 403
    assert blocked_pipeline.json()["error"]["code"] == "CONSENT_REQUIRED"
    monkeypatch.setattr(settings, "auth_user_id", "different-artist")
    assert client.get(
        f"/api/v1/analyses/{analysis_id}/agent-pipeline",
        headers=AUTH,
    ).status_code == 404


def test_v1_private_routes_require_bearer_token(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "configured-test-token")
    response = client.post("/api/v1/songs", json={"title": "Private"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers.get("X-Request-ID")


def test_v1_api_error_envelope_on_validation(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    response = client.post("/api/v1/songs", headers=AUTH, json={"title": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"]


def test_artist_onboarding_and_dashboard_are_private_and_paginated(monkeypatch):
    owner_id = "artist-platform-owner-a"
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", owner_id)
    
    # Clean up any previous test data for this owner
    db = SessionLocal()
    try:
        from backend.domain.models import ArtistWorkspaceProfile, StudioSong
        db.query(ArtistWorkspaceProfile).filter_by(owner_id=owner_id).delete()
        db.query(StudioSong).filter_by(owner_id=owner_id).delete()
        db.commit()
    finally:
        db.close()

    assert client.get("/api/v1/artist/profile", headers=AUTH).json() is None
    invalid_profile = client.put(
        "/api/v1/artist/profile",
        headers=AUTH,
        json={"display_name": ""},
    )
    assert invalid_profile.status_code == 422

    profile_payload = {
        "display_name": "Nova Echo",
        "bio": "Independent electronic artist.",
        "primary_genre": "electronic",
        "language": "English",
        "territories": ["United States", "Canada"],
        "goals": ["finish an EP", "grow a live audience"],
        "brand_voice": "Direct and curious.",
    }
    saved_profile = client.put(
        "/api/v1/artist/profile",
        headers=AUTH,
        json=profile_payload,
    )
    assert saved_profile.status_code == 200, saved_profile.text
    assert saved_profile.json()["display_name"] == "Nova Echo"
    assert saved_profile.json()["territories"] == ["United States", "Canada"]
    assert client.get("/api/v1/artist/profile", headers=AUTH).json()["profile_id"] == saved_profile.json()["profile_id"]
    completed_at = saved_profile.json()["onboarding_completed_at"]
    edited_profile = client.put(
        "/api/v1/artist/profile",
        headers=AUTH,
        json={**profile_payload, "bio": "Updated artist biography."},
    )
    assert edited_profile.json()["bio"] == "Updated artist biography."
    assert edited_profile.json()["onboarding_completed_at"] == completed_at

    song_ids = []
    for title in ("First Song", "Second Song", "Third Song"):
        created = client.post("/api/v1/songs", headers=AUTH, json={"title": title})
        assert created.status_code == 201
        song_ids.append(created.json()["song_id"])
        assert created.json()["artist_name"] == "Nova Echo"
        assert created.json()["language"] == "English"
        assert created.json()["genre_preferences"] == ["electronic"]

    first_page = client.get("/api/v1/songs?limit=2", headers=AUTH)
    assert first_page.status_code == 200, first_page.text
    assert first_page.json()["total_count"] == 3
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["next_cursor"]
    second_page = client.get(
        f"/api/v1/songs?limit=2&cursor={first_page.json()['next_cursor']}",
        headers=AUTH,
    )
    assert second_page.status_code == 200, second_page.text
    first_ids = {item["song_id"] for item in first_page.json()["items"]}
    second_ids = {item["song_id"] for item in second_page.json()["items"]}
    assert len(second_ids) == 1
    assert first_ids.isdisjoint(second_ids)
    assert first_ids | second_ids == set(song_ids)

    monkeypatch.setattr(settings, "auth_user_id", "artist-platform-owner-b")
    assert client.get("/api/v1/artist/profile", headers=AUTH).json() is None
    assert client.get("/api/v1/songs", headers=AUTH).json()["total_count"] == 0
    assert client.get(f"/api/v1/songs/{song_ids[0]}", headers=AUTH).status_code == 404

    invalid_cursor = client.get("/api/v1/songs?cursor=bad-cursor", headers=AUTH)
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["code"] == "VALIDATION_ERROR"


def test_media_requires_rights_and_withdrawable_processing_consent(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", "media-rights-owner-a")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    song = client.post("/api/v1/songs", headers=AUTH, json={"title": "Permissioned Track"})
    song_id = song.json()["song_id"]
    upload_request = {
        "filename": "track.wav",
        "declared_content_type": "audio/wav",
        "size_bytes": 3,
        "asset_kind": "audio_original",
    }
    missing_rights = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json=upload_request,
    )
    assert missing_rights.status_code == 403
    assert missing_rights.json()["error"]["code"] == "RIGHTS_DECLARATION_REQUIRED"

    declaration = client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "licensed",
            "composition_rights_basis": "authorized",
            "rights_confirmed": True,
        },
    )
    assert declaration.status_code == 201
    missing_consent = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json=upload_request,
    )
    assert missing_consent.status_code == 403
    assert missing_consent.json()["error"]["code"] == "CONSENT_REQUIRED"

    consent = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "audio_processing", "song_id": song_id},
    )
    assert consent.status_code == 201
    intent = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json=upload_request,
    )
    assert intent.status_code == 201
    asset_id = intent.json()["asset_id"]

    withdrawal = client.post(
        f"/api/v1/consents/{consent.json()['consent_id']}/withdraw",
        headers=AUTH,
    )
    assert withdrawal.status_code == 200
    assert withdrawal.json()["granted"] is False
    blocked_upload = client.put(
        f"/api/v1/assets/{asset_id}/upload",
        headers=AUTH,
        content=b"123",
    )
    assert blocked_upload.status_code == 403
    assert blocked_upload.json()["error"]["code"] == "CONSENT_REQUIRED"

    monkeypatch.setattr(settings, "auth_user_id", "media-rights-owner-b")
    assert client.get("/api/v1/consents", headers=AUTH).json()["items"] == []
    assert client.get("/api/v1/rights/declarations", headers=AUTH).json()["items"] == []
    assert client.post(
        f"/api/v1/consents/{consent.json()['consent_id']}/withdraw",
        headers=AUTH,
    ).status_code == 404


def test_openrouter_is_not_selected_without_third_party_consent(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-only-key")
    monkeypatch.setattr(settings, "openrouter_model", "test-only-model")

    from backend.services.ai_provider import (
        MockReportProvider,
        OpenRouterReportProvider,
        get_report_provider,
    )

    assert isinstance(get_report_provider(), MockReportProvider)
    assert isinstance(get_report_provider(allow_external=True), OpenRouterReportProvider)


def test_openrouter_does_not_receive_artist_supplied_lyrics(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "test-only-key")
    monkeypatch.setattr(settings, "openrouter_model", "test-only-model")
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Evidence-limited report.",
                                    "strengths": [],
                                    "improvement_opportunities": [],
                                    "hook_candidates": [],
                                    "recommendations": [],
                                    "limitations": [],
                                }
                            )
                        }
                    }
                ]
            }

    def fake_post(_url, **kwargs):
        captured["context"] = json.loads(kwargs["json"]["messages"][1]["content"])
        return Response()

    from backend.services import ai_provider

    monkeypatch.setattr(ai_provider.httpx, "post", fake_post)
    intelligence = {
        "audio_features": {"duration_seconds": {"value": 42.5, "status": "measured"}},
        "sections": [],
        "hook_candidates": [
            {
                "kind": "lyrical",
                "text": "Private lyric text",
                "evidence": "Repeated in artist-supplied lyrics.",
            }
        ],
        "lyrics_analysis": {
            "available": True,
            "themes": ["loss and longing"],
            "candidate_lines": [{"text": "Private lyric text"}],
        },
        "predictions": [],
        "limitations": [],
        "provenance": [],
    }

    ai_provider.OpenRouterReportProvider().generate("Test song", intelligence)

    sent = captured["context"]["song_intelligence"]
    assert sent["lyrics_analysis"]["status"] == "not_shared"
    assert sent["lyrics_analysis"]["candidate_lines"] == []
    assert sent["hook_candidates"] == []
    assert "Private lyric text" not in json.dumps(captured["context"])


def test_release_plan_is_idempotent_owner_scoped_and_approval_is_non_executing(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", "release-planner-owner")
    song = client.post("/api/v1/songs", headers=AUTH, json={"title": "Next Chapter"})
    assert song.status_code == 201, song.text
    song_id = song.json()["song_id"]
    payload = {
        "song_id": song_id,
        "release_date": "2030-06-15",
        "goal": "Share the single with existing listeners",
    }
    headers = {**AUTH, "Idempotency-Key": "release-plan-test-key"}

    created = client.post("/api/v1/release-plans", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    plan = created.json()
    assert plan["status"] == "draft"
    assert len(plan["tasks"]) == 7
    assert plan["tasks"][4]["planned_date"] == "2030-06-15"
    assert all("cost" not in task for task in plan["tasks"])

    replay = client.post("/api/v1/release-plans", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.json()["plan_id"] == plan["plan_id"]
    conflict = client.post(
        "/api/v1/release-plans",
        headers=headers,
        json={**payload, "goal": "A different goal"},
    )
    assert conflict.status_code == 409

    approved = client.post(f"/api/v1/release-plans/{plan['plan_id']}/approve", headers=AUTH)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_at"] is not None
    locked = client.patch(
        f"/api/v1/release-plans/{plan['plan_id']}",
        headers=AUTH,
        json={"goal": "Change after approval"},
    )
    assert locked.status_code == 409
    assert len(client.get(f"/api/v1/songs/{song_id}/release-plans", headers=AUTH).json()["items"]) == 1

    monkeypatch.setattr(settings, "auth_user_id", "another-owner")
    hidden = client.get(f"/api/v1/release-plans/{plan['plan_id']}", headers=AUTH)
    assert hidden.status_code == 404


import time


def wait_for_job_status(client, auth_headers, status_url, timeout=30, poll_interval=0.5):
    """Poll job status from status_url until terminal state or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(status_url, headers=auth_headers)
        if resp.status_code == 200:
            status = resp.json().get("status")
            if status not in ("queued", "running"):
                return status
        time.sleep(poll_interval)
    return None





def test_asset_verification_job_executes_automatically(monkeypatch, tmp_path):
    """Verify asset verification jobs execute automatically without manual run_v1_job() invocation."""
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", "test-asset-auto")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)

    from backend.services import job_runner

    monkeypatch.setattr(
        job_runner,
        "verify_audio",
        lambda _key: {
            "duration_seconds": 42.5,
            "sample_rate": 44100,
            "channels": 2,
            "actual_content_type": "audio/wav",
        },
    )

    # Create song
    created = client.post("/api/v1/songs", headers=AUTH, json={"title": "AutoVer"})
    assert created.status_code == 201
    song_id = created.json()["song_id"]

    # Rights declaration
    client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "authorized",
            "rights_confirmed": True,
        },
    )

    # Consent for audio processing
    client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={"consent_type": "audio_processing", "song_id": song_id},
    )

    # Upload asset
    intent = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json={
            "filename": "test.wav",
            "declared_content_type": "audio/wav",
            "size_bytes": 12,
            "asset_kind": "audio_original",
        },
    )
    assert intent.status_code == 201, f"Got {intent.status_code}: {intent.text}"
    asset_id = intent.json()["asset_id"]
    client.put(f"/api/v1/assets/{asset_id}/upload", headers=AUTH, content=b"123456789012")

    # Complete asset (triggers verification job)
    completed = client.post(
        f"/api/v1/songs/{song_id}/assets/complete",
        headers=AUTH,
        json={"asset_id": asset_id},
    )
    assert completed.status_code == 202
    status_url = completed.json()["status_url"]

    # Poll for job completion - this verifies automatic execution!
    final_status = wait_for_job_status(client, AUTH, status_url, timeout=15)
    assert final_status == "succeeded", f"Expected succeeded, got {final_status}. Job executed automatically!"


def test_failed_job_does_not_stay_running(monkeypatch, tmp_path):
    """Verify failed jobs transition from running to failed state."""
    monkeypatch.setattr(settings, "api_token", "test-studio-token")
    monkeypatch.setattr(settings, "auth_user_id", "test-fail")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    monkeypatch.setattr(settings, "ai_provider", "mock")

    from backend.services import job_runner
    from backend.core.errors import ApiError

    monkeypatch.setattr(
        job_runner,
        "verify_audio",
        lambda _key: {
            "duration_seconds": 42.5,
            "sample_rate": 44100,
            "channels": 2,
            "actual_content_type": "audio/wav",
        },
    )

    def fail_extract(*args, **kwargs):
        raise ApiError("EXTRACTION_FAILED", "Simulated failure")

    monkeypatch.setattr(job_runner, "extract_features", fail_extract)

    # Create song, consent, and upload
    created = client.post("/api/v1/songs", headers=AUTH, json={"title": "FailTest"})
    song_id = created.json()["song_id"]

    client.post("/api/v1/consents", headers=AUTH, json={"consent_type": "audio_processing", "song_id": song_id})
    client.post("/api/v1/consents", headers=AUTH, json={"consent_type": "derived_analysis_storage", "song_id": song_id})
    client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "authorized",
            "rights_confirmed": True,
        },
    )

    intent = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json={
            "filename": "test.wav",
            "declared_content_type": "audio/wav",
            "size_bytes": 12,
            "asset_kind": "audio_original",
        },
    )
    asset_id = intent.json()["asset_id"]
    client.put(f"/api/v1/assets/{asset_id}/upload", headers=AUTH, content=b"123456789012")
    client.post(f"/api/v1/songs/{song_id}/assets/complete", headers=AUTH, json={"asset_id": asset_id})
    time.sleep(2)

    # Request analysis (will fail during extraction)
    analysis_resp = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": "fail-test"},
        json={
            "asset_id": asset_id,
            "analysis_profile": "standard_v1",
            "generate_ai_report": False,
        },
    )
    assert analysis_resp.status_code == 202
    analysis_id = analysis_resp.json()["analysis_id"]

    # Wait for scheduler to pick up and fail
    final_status = wait_for_job_status(client, AUTH, analysis_resp.json()["status_url"], timeout=15)
    assert final_status == "failed", f"Expected failed, got {final_status}. Job did not stay running!"

