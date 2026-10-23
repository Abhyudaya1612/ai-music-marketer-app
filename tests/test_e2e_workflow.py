"""End-to-end workflow tests: song creation → upload → verification → analysis → report."""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='_e2e.db')}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time

from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.database import SessionLocal
from backend.domain.models import SongAnalysis, AnalysisReport

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-e2e-token"}


def wait_for_job_status(client, headers, status_url, timeout=30):
    """Poll status endpoint until job reaches terminal state or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        response = client.get(status_url, headers=headers)
        if response.status_code == 200:
            status = response.json().get("status")
            if status in ("succeeded", "failed"):
                return status
        time.sleep(0.5)
    raise TimeoutError(f"Job did not reach terminal state within {timeout}s")


def test_e2e_song_upload_analysis_report_with_mocked_audio(monkeypatch, tmp_path):
    """End-to-end workflow: create song → upload → verify → analyze → generate report.
    
    This test uses mocked audio processing to verify the full workflow without FFmpeg.
    """
    monkeypatch.setattr(settings, "api_token", "test-e2e-token")
    monkeypatch.setattr(settings, "auth_user_id", "test-e2e-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    
    from backend.services import job_runner
    
    # Mock audio processing functions
    monkeypatch.setattr(
        job_runner,
        "verify_audio",
        lambda _key: {
            "duration_seconds": 180.5,
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
                    "value": 180.5,
                    "status": "measured",
                    "unit": "seconds",
                    "source": "ffprobe",
                    "source_version": "ffmpeg-version-x",
                    "limitations": [],
                },
                "sample_rate_hz": {
                    "value": 44100,
                    "status": "measured",
                    "unit": "Hz",
                    "source": "ffprobe",
                    "source_version": "ffmpeg-version-x",
                    "limitations": [],
                },
                "channels": {
                    "value": 2,
                    "status": "measured",
                    "unit": "channels",
                    "source": "ffprobe",
                    "source_version": "ffmpeg-version-x",
                    "limitations": [],
                },
                "tempo_bpm": {
                    "value": 120.0,
                    "status": "estimated",
                    "unit": "bpm",
                    "source": "librosa",
                    "source_version": "librosa-0.10.0",
                    "limitations": ["Tempo is an algorithmic estimate and should be reviewed by the artist."],
                },
                "rms_energy": {
                    "value": 0.152,
                    "status": "derived",
                    "unit": "normalized amplitude",
                    "source": "librosa",
                    "source_version": "librosa-0.10.0",
                    "limitations": ["RMS is a signal-level descriptor, not a subjective quality score."],
                },
                "musical_key": {
                    "value": "C major",
                    "status": "estimated",
                    "unit": None,
                    "source": "essentia",
                    "source_version": None,
                    "limitations": ["Key is an algorithmic estimate; mode and ambiguity are not represented."],
                },
            },
            "sections": [
                {
                    "label": "unknown",
                    "start_seconds": 0.0,
                    "end_seconds": 45.2,
                    "evidence": "This segment is separated by a detected silence gap; its musical role is undetermined.",
                },
                {
                    "label": "unknown",
                    "start_seconds": 50.1,
                    "end_seconds": 120.5,
                    "evidence": "This segment is separated by a detected silence gap; its musical role is undetermined.",
                },
            ],
            "hook_candidates": [],
            "lyrics_analysis": {
                "available": False,
                "status": "unavailable",
                "themes": [],
                "candidate_lines": [],
                "reason": "No lyrics were supplied for this analysis.",
            },
            "predictions": [],
            "limitations": [
                "This analysis reports file measurements and available signal features only.",
                "No listener performance data or private platform data was available.",
            ],
            "provenance": [
                {
                    "component": "audio_pipeline",
                    "version": "standard_v1",
                    "input_checksum_sha256": checksum,
                },
                {
                    "component": "silence_segment_detection",
                    "version": "ffmpeg-version-x",
                    "threshold_dbfs": -35,
                    "minimum_silence_seconds": 0.75,
                },
            ],
        },
    )
    
    # Step 1: Create song
    song_response = client.post(
        "/api/v1/songs",
        headers=AUTH,
        json={
            "title": "Test Song E2E",
            "artist_name": "Test Artist",
            "language": "en",
            "genre_preferences": ["pop", "electronic"],
        },
    )
    assert song_response.status_code == 201, f"Failed to create song: {song_response.text}"
    song_id = song_response.json()["song_id"]
    assert song_id is not None
    
    # Step 2: Create rights declaration
    rights_response = client.post(
        "/api/v1/rights/declarations",
        headers=AUTH,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "owned",
            "rights_confirmed": True,
        },
    )
    assert rights_response.status_code == 201, f"Failed to create rights declaration: {rights_response.text}"
    
    # Step 3: Grant audio processing consent
    consent_response = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={
            "consent_type": "audio_processing",
            "song_id": song_id,
        },
    )
    assert consent_response.status_code == 201, f"Failed to grant consent: {consent_response.text}"
    
    # Step 4: Get upload intent
    intent_response = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=AUTH,
        json={
            "filename": "test-song.wav",
            "declared_content_type": "audio/wav",
            "size_bytes": 1024,
            "asset_kind": "audio_original",
        },
    )
    assert intent_response.status_code == 201, f"Failed to get upload intent: {intent_response.text}"
    asset_id = intent_response.json()["asset_id"]
    
    # Step 5: Upload audio data
    upload_response = client.put(
        f"/api/v1/assets/{asset_id}/upload",
        headers=AUTH,
        content=b"x" * 1024,
    )
    assert upload_response.status_code in (200, 204), f"Failed to upload asset: {upload_response.text}"
    
    # Step 6: Complete upload (triggers asset verification job)
    complete_response = client.post(
        f"/api/v1/songs/{song_id}/assets/complete",
        headers=AUTH,
        json={"asset_id": asset_id},
    )
    assert complete_response.status_code == 202, f"Failed to complete upload: {complete_response.text}"
    verification_status_url = complete_response.json()["status_url"]
    
    # Step 7: Wait for asset verification job to complete
    verification_status = wait_for_job_status(client, AUTH, verification_status_url, timeout=15)
    assert verification_status == "succeeded", f"Asset verification job failed: {verification_status}"
    
    # Step 8: Grant derived analysis storage consent
    analysis_consent_response = client.post(
        "/api/v1/consents",
        headers=AUTH,
        json={
            "consent_type": "derived_analysis_storage",
            "song_id": song_id,
        },
    )
    assert analysis_consent_response.status_code == 201, f"Failed to grant analysis consent: {analysis_consent_response.text}"
    
    # Step 9: Trigger song analysis
    import uuid
    analysis_response = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**AUTH, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "asset_id": asset_id,
            "generate_ai_report": True,
            "allow_third_party_ai": False,
        },
    )
    assert analysis_response.status_code == 202, f"Failed to trigger analysis: {analysis_response.text}"
    analysis_id = analysis_response.json()["analysis_id"]
    analysis_status_url = analysis_response.json()["status_url"]
    
    # Step 10: Wait for analysis job to complete
    analysis_status = wait_for_job_status(client, AUTH, analysis_status_url, timeout=15)
    assert analysis_status == "succeeded", f"Analysis job failed: {analysis_status}"
    
    # Step 11: Retrieve Song Intelligence (extracted features)
    intelligence_response = client.get(
        f"/api/v1/analyses/{analysis_id}/intelligence",
        headers=AUTH,
    )
    assert intelligence_response.status_code == 200, f"Failed to retrieve intelligence: {intelligence_response.text}"
    intelligence_data = intelligence_response.json()
    
    # Verify audio_features schema
    assert "audio_features" in intelligence_data
    assert "duration_seconds" in intelligence_data["audio_features"]
    assert intelligence_data["audio_features"]["duration_seconds"]["status"] == "measured"
    assert intelligence_data["audio_features"]["duration_seconds"]["value"] == 180.5
    assert intelligence_data["audio_features"]["sample_rate_hz"]["value"] == 44100
    assert intelligence_data["audio_features"]["channels"]["value"] == 2
    
    # Verify tempo (estimated)
    assert intelligence_data["audio_features"]["tempo_bpm"]["status"] == "estimated"
    assert intelligence_data["audio_features"]["tempo_bpm"]["value"] == 120.0
    
    # Verify sections
    assert "sections" in intelligence_data
    assert len(intelligence_data["sections"]) == 2
    assert intelligence_data["sections"][0]["label"] == "unknown"
    
    # Verify provenance
    assert "provenance" in intelligence_data
    assert len(intelligence_data["provenance"]) > 0
    
    # Step 12: Retrieve A&R Report
    report_response = client.get(
        f"/api/v1/analyses/{analysis_id}/report",
        headers=AUTH,
    )
    assert report_response.status_code == 200, f"Failed to retrieve report: {report_response.text}"
    report_data = report_response.json()
    
    # Verify report structure
    assert "report_id" in report_data
    assert "analysis_id" in report_data
    assert report_data["analysis_id"] == analysis_id
    assert "summary" in report_data
    assert "strengths" in report_data
    assert "improvement_opportunities" in report_data
    assert "recommendations" in report_data
    assert "provider" in report_data
    assert report_data["provider"] == "mock"
    
    # Verify report integrity: all evidence_refs should point to available audio_features
    all_feature_keys = set(intelligence_data["audio_features"].keys())
    # Some refs use 'audio_features.' prefix, others don't
    all_feature_keys_with_prefix = {f"audio_features.{k}" for k in all_feature_keys}
    all_valid_refs = all_feature_keys | all_feature_keys_with_prefix
    for claim in report_data.get("strengths", []):
        for ref in claim.get("evidence_refs", []):
            assert ref in all_valid_refs, f"Report references unavailable feature: {ref} (available: {all_valid_refs})"
    
    print(f"\n✓ End-to-end workflow completed successfully")
    print(f"  Song ID: {song_id}")
    print(f"  Asset ID: {asset_id}")
    print(f"  Analysis ID: {analysis_id}")
    print(f"  Report ID: {report_data['report_id']}")
    print(f"  Extracted features: {len(intelligence_data['audio_features'])} features")
    print(f"  Report claims: {len(report_data['strengths'])} strengths, {len(report_data['improvement_opportunities'])} improvements")


def test_e2e_consent_withdrawal_blocks_analysis(monkeypatch, tmp_path):
    """Verify that withdrawing consent blocks analysis execution."""
    monkeypatch.setattr(settings, "api_token", "test-e2e-consent")
    monkeypatch.setattr(settings, "auth_user_id", "test-e2e-consent-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media-consent"))
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    
    from backend.services import job_runner
    
    monkeypatch.setattr(
        job_runner,
        "verify_audio",
        lambda _key: {
            "duration_seconds": 120.0,
            "sample_rate": 44100,
            "channels": 2,
            "actual_content_type": "audio/wav",
        },
    )
    
    # Use separate auth header for this test
    consent_auth = {"Authorization": "Bearer test-e2e-consent"}
    
    # Create song, rights, and consent
    song_response = client.post(
        "/api/v1/songs",
        headers=consent_auth,
        json={"title": "Consent Test Song"},
    )
    song_id = song_response.json()["song_id"]
    
    client.post(
        "/api/v1/rights/declarations",
        headers=consent_auth,
        json={
            "song_id": song_id,
            "recording_rights_basis": "owned",
            "composition_rights_basis": "owned",
            "rights_confirmed": True,
        },
    )
    
    consent_response = client.post(
        "/api/v1/consents",
        headers=consent_auth,
        json={"consent_type": "audio_processing", "song_id": song_id},
    )
    consent_id = consent_response.json()["consent_id"]
    
    # Upload asset
    intent_response = client.post(
        f"/api/v1/songs/{song_id}/assets/upload-intent",
        headers=consent_auth,
        json={
            "filename": "test.wav",
            "declared_content_type": "audio/wav",
            "size_bytes": 1024,
            "asset_kind": "audio_original",
        },
    )
    asset_id = intent_response.json()["asset_id"]
    
    client.put(f"/api/v1/assets/{asset_id}/upload", headers=consent_auth, content=b"x" * 1024)
    
    # Complete upload (verification job)
    complete_response = client.post(
        f"/api/v1/songs/{song_id}/assets/complete",
        headers=consent_auth,
        json={"asset_id": asset_id},
    )
    verification_status_url = complete_response.json()["status_url"]
    
    # Wait for verification to complete
    wait_for_job_status(client, consent_auth, verification_status_url, timeout=15)
    
    # Grant analysis consent
    client.post(
        "/api/v1/consents",
        headers=consent_auth,
        json={"consent_type": "derived_analysis_storage", "song_id": song_id},
    )
    
    # Start analysis
    import uuid
    analysis_response = client.post(
        f"/api/v1/songs/{song_id}/analyses",
        headers={**consent_auth, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "asset_id": asset_id,
            "generate_ai_report": False,
        },
    )
    analysis_status_url = analysis_response.json()["status_url"]
    
    # Withdraw audio processing consent (should block ongoing analysis)
    withdraw_response = client.post(
        f"/api/v1/consents/{consent_id}/withdraw",
        headers=consent_auth,
    )
    assert withdraw_response.status_code == 200, f"Failed to withdraw consent: {withdraw_response.text}"
    
    # Wait for analysis to fail due to missing consent
    start = time.time()
    timeout = 15
    final_status = None
    while time.time() - start < timeout:
        status_response = client.get(analysis_status_url, headers=consent_auth)
        if status_response.status_code == 200:
            final_status = status_response.json().get("status")
            if final_status == "failed":
                break
        time.sleep(0.5)
    
    assert final_status == "failed", f"Analysis should fail after consent withdrawal, got {final_status}"
    print(f"\n✓ Consent withdrawal correctly blocked analysis execution")
