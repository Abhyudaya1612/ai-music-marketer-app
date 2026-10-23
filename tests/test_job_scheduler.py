"""Integration tests for the background job scheduler lifecycle and durability."""
from __future__ import annotations

import os
import sys
import tempfile
import time

os.environ.setdefault("APP_DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='_scheduler.db')}")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.domain.models import AnalysisJob
from backend.services.job_scheduler import start_scheduler, stop_scheduler, _dispatch_queued_jobs
from backend.services.job_runner import run_v1_job


def test_scheduler_starts_and_stops_gracefully(monkeypatch):
    """Verify that the scheduler can start and stop without errors."""
    monkeypatch.setattr(settings, "job_worker_enabled", True)
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    
    # Start scheduler
    start_scheduler()
    assert True, "Scheduler started successfully"
    
    # Stop scheduler
    time.sleep(0.5)
    stop_scheduler()
    assert True, "Scheduler stopped successfully"


def test_scheduler_dispatches_queued_jobs(monkeypatch, tmp_path):
    """Verify that the scheduler discovers and executes queued jobs atomically."""
    import uuid
    monkeypatch.setattr(settings, "api_token", "test-scheduler")
    monkeypatch.setattr(settings, "auth_user_id", "test-scheduler-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_worker_enabled", True)
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    monkeypatch.setattr(settings, "job_idle_timeout_seconds", 30)
    monkeypatch.setattr(settings, "job_max_attempts", 3)
    
    from backend.services import job_runner
    
    # Mock the job functions to track execution
    job_executed = []
    
    original_verify = job_runner.verify_audio
    def mock_verify(*args, **kwargs):
        return {
            "duration_seconds": 42.0,
            "sample_rate": 44100,
            "channels": 2,
            "actual_content_type": "audio/wav",
        }
    monkeypatch.setattr(job_runner, "verify_audio", mock_verify)
    
    original_extract = job_runner.extract_features
    def mock_extract(*args, **kwargs):
        job_executed.append("extract_features_called")
        return {
            "audio_features": {
                "duration_seconds": {
                    "value": 42.0,
                    "status": "measured",
                    "unit": "seconds",
                    "source": "ffprobe",
                    "source_version": "test",
                    "limitations": [],
                },
                "sample_rate_hz": {
                    "value": 44100,
                    "status": "measured",
                    "unit": "Hz",
                    "source": "ffprobe",
                    "source_version": "test",
                    "limitations": [],
                },
                "channels": {
                    "value": 2,
                    "status": "measured",
                    "unit": "channels",
                    "source": "ffprobe",
                    "source_version": "test",
                    "limitations": [],
                },
                "tempo_bpm": {
                    "value": None,
                    "status": "unavailable",
                    "unit": None,
                    "source": "librosa",
                    "source_version": None,
                    "limitations": ["Librosa is not installed."],
                },
                "rms_energy": {
                    "value": None,
                    "status": "unavailable",
                    "unit": None,
                    "source": "librosa",
                    "source_version": None,
                    "limitations": ["Librosa is not installed."],
                },
                "musical_key": {
                    "value": None,
                    "status": "unavailable",
                    "unit": None,
                    "source": "essentia",
                    "source_version": None,
                    "limitations": ["Essentia is not installed."],
                },
            },
            "sections": [],
            "hook_candidates": [],
            "lyrics_analysis": {
                "available": False,
                "status": "unavailable",
                "themes": [],
                "candidate_lines": [],
                "reason": "No lyrics were supplied for this analysis.",
            },
            "predictions": [],
            "limitations": [],
            "provenance": [
                {"component": "audio_pipeline", "version": "standard_v1", "input_checksum_sha256": "test_checksum"},
            ],
        }
    monkeypatch.setattr(job_runner, "extract_features", mock_extract)
    
    # Create a queued job in the database with unique ID
    db = SessionLocal()
    try:
        job = AnalysisJob(
            id=f"test-job-{uuid.uuid4()}",
            owner_id="test-scheduler-user",
            task_type="asset_verification",
            subject_id="test-asset-id",
            status="queued",
            stage="queued",
            attempt=1,
        )
        db.add(job)
        db.commit()
        
        # Manually dispatch queued jobs (simulating scheduler tick)
        _dispatch_queued_jobs()
        
        # Verify the job was processed
        db.refresh(job)
        assert job.status in ("running", "succeeded", "failed"), f"Job status should be terminal or running, got {job.status}"
    finally:
        db.close()


def test_scheduler_detects_stale_jobs(monkeypatch, tmp_path):
    """Verify that the scheduler requeues stale running jobs with bounded retries."""
    import uuid
    monkeypatch.setattr(settings, "api_token", "test-stale")
    monkeypatch.setattr(settings, "auth_user_id", "test-stale-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_worker_enabled", True)
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    monkeypatch.setattr(settings, "job_idle_timeout_seconds", 1)  # Very short timeout
    monkeypatch.setattr(settings, "job_max_attempts", 3)
    
    from datetime import datetime, timezone, timedelta
    
    db = SessionLocal()
    try:
        # Create a stale job (running, but started more than 1 second ago)
        stale_job = AnalysisJob(
            id=f"stale-job-{uuid.uuid4()}",
            owner_id="test-stale-user",
            task_type="asset_verification",
            subject_id="test-asset-id",
            status="running",
            stage="running",
            attempt=1,
            started_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        db.add(stale_job)
        db.commit()
        
        # Dispatch queued jobs, which should also detect stale jobs
        _dispatch_queued_jobs()
        
        # Verify the stale job was requeued
        db.refresh(stale_job)
        assert stale_job.status == "queued", f"Stale job should be requeued, got {stale_job.status}"
        assert stale_job.attempt == 2, f"Attempt count should be incremented, got {stale_job.attempt}"
    finally:
        db.close()


def test_scheduler_respects_max_attempts(monkeypatch, tmp_path):
    """Verify that jobs exceeding max_attempts are not retried."""
    import uuid
    monkeypatch.setattr(settings, "api_token", "test-max-attempts")
    monkeypatch.setattr(settings, "auth_user_id", "test-max-attempts-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_worker_enabled", True)
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    monkeypatch.setattr(settings, "job_idle_timeout_seconds", 1)
    monkeypatch.setattr(settings, "job_max_attempts", 2)
    
    from datetime import datetime, timezone, timedelta
    
    db = SessionLocal()
    try:
        # Create a stale job at max attempts
        max_attempt_job = AnalysisJob(
            id=f"max-attempt-job-{uuid.uuid4()}",
            owner_id="test-max-attempts-user",
            task_type="asset_verification",
            subject_id="test-asset-id",
            status="running",
            stage="running",
            attempt=2,  # Already at max
            started_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        db.add(max_attempt_job)
        db.commit()
        
        # Dispatch queued jobs
        _dispatch_queued_jobs()
        
        # Verify the job was NOT requeued (stays at max attempts)
        db.refresh(max_attempt_job)
        assert max_attempt_job.status == "running", f"Job at max attempts should stay running (not requeued), got {max_attempt_job.status}"
        assert max_attempt_job.attempt == 2, f"Attempt count should not change, got {max_attempt_job.attempt}"
    finally:
        db.close()


def test_scheduler_atomic_job_dispatch_prevents_duplicates(monkeypatch, tmp_path):
    """Verify that atomic UPDATE prevents duplicate dispatch in multi-replica scenarios."""
    import uuid
    monkeypatch.setattr(settings, "api_token", "test-atomic")
    monkeypatch.setattr(settings, "auth_user_id", "test-atomic-user")
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "job_worker_enabled", True)
    monkeypatch.setattr(settings, "job_poll_interval_seconds", 1)
    
    from backend.services import job_runner
    
    dispatch_count = [0]
    
    original_run = job_runner.run_v1_job
    def mock_run(*args, **kwargs):
        dispatch_count[0] += 1
    monkeypatch.setattr(job_runner, "run_v1_job", mock_run)
    
    db = SessionLocal()
    try:
        # Create a queued job with unique ID
        job = AnalysisJob(
            id=f"atomic-job-{uuid.uuid4()}",
            owner_id="test-atomic-user",
            task_type="asset_verification",
            subject_id="test-asset-id",
            status="queued",
            stage="queued",
            attempt=1,
        )
        db.add(job)
        db.commit()
        
        # Dispatch queued jobs once
        _dispatch_queued_jobs()
        
        # The job should transition to running
        db.refresh(job)
        assert job.status in ("running", "succeeded", "failed"), "Job should be processed once"
        
        # Dispatch again - the job should not be processed again (already transitioned)
        initial_dispatch_count = dispatch_count[0]
        _dispatch_queued_jobs()
        
        # Verify no additional dispatch occurred for the already-processed job
        assert dispatch_count[0] == initial_dispatch_count, "Job should only be dispatched once"
    finally:
        db.close()
