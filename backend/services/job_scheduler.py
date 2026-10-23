"""Background job scheduler for durable job execution.

This service runs a background polling loop that queries the database for queued jobs
and executes them. It ensures jobs are durably executed even if BackgroundTasks callbacks
are lost or the API container crashes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..database import SessionLocal
from ..domain.models import AnalysisJob
from .job_runner import run_v1_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_thread_pool: ThreadPoolExecutor | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dispatch_queued_jobs() -> None:
    """Query for queued jobs and execute them in background threads.
    
    Uses atomic UPDATE to transition jobs from 'queued' to 'running' to prevent
    duplicate dispatch in multi-replica deployments.
    """
    global _thread_pool
    
    def _job_done_callback(job_id: str, future):
        """Log completion or exceptions from job execution."""
        try:
            result = future.result()  # This will raise if the job raised an exception
            logger.info("job_thread_completed", extra={"job_id": job_id})
        except Exception as e:
            logger.error(
                "job_thread_failed",
                extra={"job_id": job_id, "error_type": type(e).__name__, "error": str(e)[:200]},
                exc_info=False,
            )
    
    db = SessionLocal()
    try:
        # Find all queued jobs
        queued = db.query(AnalysisJob).filter(
            AnalysisJob.status == "queued",
            AnalysisJob.attempt <= settings.job_max_attempts,
        ).all()
        
        for job in queued:
            job_id = job.id  # Capture job_id before session closes
            # Atomically transition to running
            updated = db.query(AnalysisJob).filter(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "queued",
            ).update(
                {
                    AnalysisJob.status: "running",
                    AnalysisJob.started_at: _utcnow(),
                    AnalysisJob.updated_at: _utcnow(),
                },
                synchronize_session=False,
            )
            db.commit()
            
            # Submit job to thread pool so scheduler thread doesn't block
            if updated:
                task_type = job.task_type  # Capture task_type before session closes
                logger.info("dispatch_job", extra={"job_id": job_id, "task_type": task_type})
                try:
                    if _thread_pool is None:
                        _thread_pool = ThreadPoolExecutor(max_workers=10)
                    future = _thread_pool.submit(
                        run_v1_job,
                        job_id,
                        generate_ai_report=True,
                        allow_third_party_ai=False,
                    )
                    # Add callback to log exceptions from the thread (using job_id string, not object)
                    future.add_done_callback(lambda f: _job_done_callback(job_id, f))
                except Exception as e:
                    logger.error(
                        "dispatch_job_error",
                        extra={"job_id": job_id, "error": str(e)},
                        exc_info=True,
                    )
        
        # Check for stale running jobs (timed out without finishing)
        stale_threshold = _utcnow() - timedelta(seconds=settings.job_idle_timeout_seconds)
        stale = db.query(AnalysisJob).filter(
            AnalysisJob.status == "running",
            AnalysisJob.started_at < stale_threshold,
            AnalysisJob.attempt < settings.job_max_attempts,
        ).all()
        
        for job in stale:
            job.attempt += 1
            job.status = "queued"
            job.stage = "queued"
            job.updated_at = _utcnow()
            logger.warning(
                "stale_job_requeued",
                extra={"job_id": job.id, "attempt": job.attempt},
            )
        
        db.commit()
    except Exception as e:
        logger.error("dispatch_queued_jobs_error", exc_info=True)
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background job scheduler."""
    if not settings.job_worker_enabled:
        logger.info("job_worker_disabled")
        return
    
    global _scheduler
    if _scheduler is not None:
        logger.warning("scheduler_already_running")
        return
    
    try:
        _scheduler = BackgroundScheduler()
        
        # Add the dispatch job to run every poll interval
        _scheduler.add_job(
            _dispatch_queued_jobs,
            "interval",
            seconds=settings.job_poll_interval_seconds,
            id="job_dispatcher",
            name="Poll and dispatch queued jobs",
            replace_existing=True,
        )
        
        _scheduler.start()
        
        logger.info(
            "job_scheduler_started",
            extra={
                "poll_interval_seconds": settings.job_poll_interval_seconds,
                "idle_timeout_seconds": settings.job_idle_timeout_seconds,
                "max_attempts": settings.job_max_attempts,
            },
        )
    except Exception as e:
        logger.error("job_scheduler_start_error", exc_info=True)
        _scheduler = None
        raise


def stop_scheduler() -> None:
    """Stop the background job scheduler."""
    global _scheduler, _thread_pool
    if _scheduler is None:
        return
    
    try:
        _scheduler.shutdown(wait=True)
        logger.info("job_scheduler_stopped")
    except Exception as e:
        logger.error("job_scheduler_stop_error", exc_info=True)
    finally:
        _scheduler = None
    
    # Shutdown thread pool
    if _thread_pool is not None:
        try:
            _thread_pool.shutdown(wait=True)
            logger.info("job_thread_pool_stopped")
        except Exception as e:
            logger.error("job_thread_pool_stop_error", exc_info=True)
        finally:
            _thread_pool = None
