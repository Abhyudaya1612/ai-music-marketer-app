"""Persistent in-process worker for the local first-slice jobs."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import SessionLocal
from ..domain.models import (
    AnalysisJob,
    AnalysisReport,
    MediaAsset,
    PlatformConnection,
    RightsDeclaration,
    SongAnalysis,
    StudioSong,
    VideoRender,
)
from ..domain.schemas import SongIntelligenceIn
from .ai_provider import PROMPT_VERSION, get_report_provider
from .audio import extract_features, verify_audio
from .consent import has_active_consent
from .storage import original_path, render_output_path
from .video_rendering import VideoRenderError, render_motion_graphics
from .lyric_video_generator import render_lyric_video, LyricVideoError
from .ollama_provider import generate_metadata
from .youtube_publisher import publish_to_youtube, YouTubePublishError
from .platform_oauth import decrypt_token

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fail_job(db: Session, job: AnalysisJob, error_code: str, analysis: SongAnalysis | None = None) -> None:
    now = _utcnow()
    job.status = "failed"
    job.stage = "failed"
    job.error_code = error_code
    job.finished_at = now
    job.updated_at = now
    logger.warning("job_failed", extra={"job_id": job.id, "error_code": error_code})
    if analysis is not None:
        analysis.status = "failed"
        analysis.stage = "failed"
        analysis.error_code = error_code
        analysis.progress_percent = 100
        analysis.updated_at = now


def run_v1_job(
    job_id: str,
    generate_ai_report: bool = True,
    allow_third_party_ai: bool = False,
) -> None:
    """Run one durable job and record every terminal outcome in the database."""
    db = SessionLocal()
    _job_start = time.monotonic()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job is None:
            return
        # Job status is already "running" - set by scheduler before dispatch
        # Update stage only
        job.stage = "starting"
        job.updated_at = _utcnow()
        db.commit()
        logger.info("job_started", extra={"job_id": job_id, "task_type": job.task_type})
        
        # Log before dispatching
        import sys
        print(f"[JOB_DISPATCH] Dispatching {job.task_type} job {job_id[:8]}...", file=sys.stderr, flush=True)
        
        if job.task_type == "asset_verification":
            _verify_asset_job(db, job)
        elif job.task_type == "song_analysis":
            _analysis_job(db, job, generate_ai_report, allow_third_party_ai)
        elif job.task_type == "video_render":
            _video_render_job(db, job)
        elif job.task_type == "lyric_video_render":
            _lyric_video_render_job(db, job)
        elif job.task_type == "youtube_publish":
            print(f"[JOB_DISPATCH] About to call _youtube_publish_job", file=sys.stderr, flush=True)
            _youtube_publish_job(db, job)
            print(f"[JOB_DISPATCH] _youtube_publish_job returned", file=sys.stderr, flush=True)
        else:
            _fail_job(db, job, "INTERNAL_ERROR")
            db.commit()
    except Exception as exc:
        import sys
        print(f"[JOB_ERROR] Exception in run_v1_job: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr, flush=True)
        logger.error("First-slice job failed job_id=%s exception_type=%s", job_id, type(exc).__name__)
        try:
            db.rollback()
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job is not None and job.status not in {"succeeded", "failed"}:
                analysis = (
                    db.query(SongAnalysis).filter(SongAnalysis.id == job.subject_id).first()
                    if job.task_type == "song_analysis"
                    else None
                )
                if job.task_type == "video_render":
                    render = db.query(VideoRender).filter(VideoRender.id == job.subject_id).first()
                    _fail_video_job(db, job, render, "INTERNAL_ERROR")
                elif job.task_type == "youtube_publish":
                    render = db.query(VideoRender).filter(VideoRender.id == job.subject_id).first()
                    _fail_video_job(db, job, render, "INTERNAL_ERROR")
                else:
                    _fail_job(db, job, "INTERNAL_ERROR", analysis)
                db.commit()
        except Exception as persist_exc:
            logger.error(
                "Unable to persist job failure job_id=%s exception_type=%s",
                job_id,
                type(persist_exc).__name__,
            )
            db.rollback()
    finally:
        db.close()


def _verify_asset_job(db: Session, job: AnalysisJob) -> None:
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == job.subject_id,
        MediaAsset.owner_id == job.owner_id,
    ).first()
    if asset is None:
        _fail_job(db, job, "RESOURCE_NOT_FOUND")
        db.commit()
        return
    if not _has_rights_declaration(db, job.owner_id, asset.song_id) or not has_active_consent(
        db,
        job.owner_id,
        "audio_processing",
        asset.song_id,
    ):
        asset.status = "blocked"
        _fail_job(db, job, "CONSENT_REQUIRED")
        db.commit()
        return
    try:
        _verify_start = time.monotonic()
        metadata = verify_audio(asset.storage_key)
        asset.duration_seconds = metadata["duration_seconds"]
        asset.actual_content_type = metadata["actual_content_type"]
        asset.status = "ready"
        job.status = "succeeded"
        job.stage = "completed"
        job.finished_at = _utcnow()
        job.updated_at = job.finished_at
        logger.info("job_completed", extra={
            "job_id": job.id,
            "task_type": job.task_type,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - _verify_start) * 1000),
        })
        db.commit()
    except ApiError as exc:
        asset.status = "failed"
        _fail_job(db, job, exc.code)
        db.commit()


def _analysis_job(
    db: Session,
    job: AnalysisJob,
    generate_ai_report: bool,
    allow_third_party_ai: bool,
) -> None:
    analysis = db.query(SongAnalysis).filter(
        SongAnalysis.id == job.subject_id,
        SongAnalysis.owner_id == job.owner_id,
    ).first()
    if analysis is None:
        _fail_job(db, job, "RESOURCE_NOT_FOUND")
        db.commit()
        return
    analysis.status = "running"
    analysis.stage = "audio_processing"
    analysis.progress_percent = 10
    analysis.updated_at = _utcnow()
    job.stage = analysis.stage
    job.updated_at = analysis.updated_at
    db.commit()
    logger.info("job_stage", extra={"job_id": job.id, "stage": "audio_processing"})
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == analysis.asset_id,
        MediaAsset.owner_id == job.owner_id,
        MediaAsset.status == "ready",
    ).first()
    song = db.query(StudioSong).filter(
        StudioSong.id == analysis.song_id,
        StudioSong.owner_id == job.owner_id,
    ).first()
    if asset is None or song is None:
        _fail_job(db, job, "RESOURCE_NOT_FOUND", analysis)
        db.commit()
        return
    if (
        not _has_rights_declaration(db, job.owner_id, song.id)
        or not has_active_consent(db, job.owner_id, "audio_processing", song.id)
        or not has_active_consent(db, job.owner_id, "derived_analysis_storage", song.id)
    ):
        _fail_job(db, job, "CONSENT_REQUIRED", analysis)
        db.commit()
        return
    _analysis_start = time.monotonic()
    try:
        intelligence = extract_features(asset.storage_key, asset.checksum_sha256 or "")
        
        # Validate schema before proceeding
        try:
            SongIntelligenceIn(**intelligence)
        except Exception as schema_exc:
            logger.error("song_intelligence_schema_validation_failed reason=%s", str(schema_exc), exc_info=True)
            raise ApiError(400, "INVALID_ANALYSIS_SCHEMA", f"Extracted features do not match expected schema: {str(schema_exc)}")
        
        intelligence["lyrics_analysis"] = (
            analysis.lyrics.analysis_json if analysis.lyrics is not None else {
                "available": False,
                "status": "unavailable",
                "themes": [],
                "candidate_lines": [],
                "reason": "No lyrics were supplied for this analysis.",
            }
        )
        if intelligence["lyrics_analysis"]["available"]:
            intelligence["provenance"].append(
                {
                    "component": "lyrics_analysis",
                    "version": "lyrics_keyword_v1",
                    "source": "artist_supplied",
                }
            )
            intelligence["hook_candidates"] = [
                {
                    "start_seconds": None,
                    "end_seconds": None,
                    "kind": "lyrical",
                    "text": candidate["text"],
                    "evidence": candidate["evidence"],
                }
                for candidate in intelligence["lyrics_analysis"]["candidate_lines"]
            ]
        analysis.stage = "validating_features"
        analysis.progress_percent = 75
        analysis.updated_at = _utcnow()
        job.stage = analysis.stage
        job.updated_at = analysis.updated_at
        db.commit()
        logger.info("job_stage", extra={"job_id": job.id, "stage": "validating_features"})

        provider_name = "none"
        provider_model = None
        if generate_ai_report:
            analysis.stage = "generating_report"
            analysis.progress_percent = 85
            analysis.updated_at = _utcnow()
            job.stage = analysis.stage
            job.updated_at = analysis.updated_at
            db.commit()
            logger.info("job_stage", extra={"job_id": job.id, "stage": "generating_report"})
            external_consent_active = allow_third_party_ai and has_active_consent(
                db,
                job.owner_id,
                "third_party_ai",
                song.id,
            )
            provider = get_report_provider(allow_external=external_consent_active)
            report_payload = provider.generate(song.title, intelligence)
            provider_name = provider.name
            provider_model = provider.model
        else:
            report_payload = None

        analysis.intelligence_json = intelligence
        analysis.status = "succeeded"
        analysis.stage = "completed"
        analysis.progress_percent = 100
        analysis.updated_at = _utcnow()
        job.status = "succeeded"
        job.stage = "completed"
        job.finished_at = analysis.updated_at
        job.updated_at = analysis.updated_at
        if report_payload is not None:
            db.add(
                AnalysisReport(
                    analysis_id=analysis.id,
                    provider=provider_name,
                    model=provider_model,
                    prompt_version=PROMPT_VERSION,
                    payload=report_payload.model_dump(mode="json"),
                )
            )
        logger.info("job_completed", extra={
            "job_id": job.id,
            "task_type": job.task_type,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - _analysis_start) * 1000),
        })
        db.commit()
    except ApiError as exc:
        _fail_job(db, job, exc.code, analysis)
        db.commit()
    except Exception:
        raise


def _fail_video_job(
    db: Session,
    job: AnalysisJob,
    render: VideoRender | None,
    error_code: str,
) -> None:
    now = _utcnow()
    job.status = "failed"
    job.stage = "failed"
    job.error_code = error_code
    job.finished_at = now
    job.updated_at = now
    logger.warning("job_failed", extra={"job_id": job.id, "error_code": error_code})
    if render is not None:
        render.status = "failed"
        render.stage = "failed"
        render.error_code = error_code
        render.updated_at = now
        render.completed_at = now


def _video_render_job(db: Session, job: AnalysisJob) -> None:
    render = db.query(VideoRender).filter(
        VideoRender.id == job.subject_id,
        VideoRender.owner_id == job.owner_id,
    ).first()
    if render is None:
        _fail_video_job(db, job, None, "RESOURCE_NOT_FOUND")
        db.commit()
        return
    render.status = "running"
    render.stage = "checking_authorization"
    render.progress_percent = 5
    render.updated_at = _utcnow()
    job.stage = render.stage
    job.updated_at = render.updated_at
    db.commit()

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == render.asset_id,
        MediaAsset.song_id == render.song_id,
        MediaAsset.owner_id == job.owner_id,
        MediaAsset.status == "ready",
    ).first()
    song = db.query(StudioSong).filter(
        StudioSong.id == render.song_id,
        StudioSong.owner_id == job.owner_id,
    ).first()
    if asset is None or song is None or asset.duration_seconds is None:
        _fail_video_job(db, job, render, "RESOURCE_NOT_FOUND")
        db.commit()
        return

    def authorization_is_active() -> bool:
        return (
            _has_rights_declaration(db, job.owner_id, song.id)
            and has_active_consent(db, job.owner_id, "audio_processing", song.id)
            and has_active_consent(db, job.owner_id, "promotional_asset_generation", song.id)
        )

    def update_progress(percent: int) -> None:
        if not authorization_is_active():
            raise VideoRenderError("CONSENT_REQUIRED")
        now = _utcnow()
        render.status = "running"
        render.stage = "rendering"
        render.progress_percent = min(95, max(render.progress_percent, percent))
        render.updated_at = now
        job.stage = render.stage
        job.updated_at = now
        db.commit()

    if not authorization_is_active():
        _fail_video_job(db, job, render, "CONSENT_REQUIRED")
        db.commit()
        return

    _render_start = time.monotonic()
    try:
        render.stage = "rendering"
        render.progress_percent = 10
        render.updated_at = _utcnow()
        job.stage = render.stage
        job.updated_at = render.updated_at
        db.commit()
        logger.info("job_stage", extra={"job_id": job.id, "stage": "rendering"})
        result = render_motion_graphics(
            source_path=original_path(asset.storage_key),
            render_id=render.id,
            render_format=render.render_format,
            title=song.title,
            artist_name=song.artist_name,
            duration_seconds=asset.duration_seconds,
            progress_callback=update_progress,
        )
        if not authorization_is_active():
            raise VideoRenderError("CONSENT_REQUIRED")
        now = _utcnow()
        result["provenance"]["source_asset_id"] = asset.id
        result["provenance"]["source_sha256"] = asset.checksum_sha256
        render.status = "succeeded"
        render.stage = "completed"
        render.progress_percent = 100
        render.provenance_json = result["provenance"]
        render.render_settings_json = result["render_settings"]
        render.scene_plan_json = result["scene_plan"]
        render.output_metadata_json = result["metadata"]
        render.output_checksum_sha256 = result["checksum_sha256"]
        render.output_size_bytes = result["size_bytes"]
        render.updated_at = now
        render.completed_at = now
        job.status = "succeeded"
        job.stage = "completed"
        job.finished_at = now
        job.updated_at = now
        logger.info("job_completed", extra={
            "job_id": job.id,
            "task_type": job.task_type,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - _render_start) * 1000),
        })
        db.commit()
    except VideoRenderError as exc:
        _fail_video_job(db, job, render, exc.code)
        db.commit()


def _has_rights_declaration(db: Session, owner_id: str, song_id: str) -> bool:
    return (
        db.query(RightsDeclaration.id)
        .filter(
            RightsDeclaration.owner_id == owner_id,
            RightsDeclaration.song_id == song_id,
        )
        .first()
        is not None
    )


def _classify_error(error_code: str) -> bool:
    """Classify error as recoverable (True) or permanent (False)."""
    recoverable_errors = {
        "YT_QUOTA_EXCEEDED",
        "YT_SERVER_ERROR",
        "RENDER_TIMEOUT",
        "FFMPEG_RENDER_FAILED",
        "RENDER_ERROR",
    }
    return error_code in recoverable_errors


def _lyric_video_render_job(db: Session, job: AnalysisJob) -> None:
    """Render a lyric video from an audio asset."""
    render = db.query(VideoRender).filter(
        VideoRender.id == job.subject_id,
        VideoRender.owner_id == job.owner_id,
    ).first()
    if render is None:
        _fail_video_job(db, job, None, "RESOURCE_NOT_FOUND")
        db.commit()
        return

    render.status = "running"
    render.stage = "preparing"
    render.progress_percent = 5
    render.updated_at = _utcnow()
    job.stage = render.stage
    job.updated_at = render.updated_at
    db.commit()

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == render.asset_id,
        MediaAsset.owner_id == job.owner_id,
        MediaAsset.status == "ready",
    ).first()
    if asset is None:
        _fail_video_job(db, job, render, "RESOURCE_NOT_FOUND")
        db.commit()
        return

    _render_start = time.monotonic()
    try:
        render.stage = "rendering"
        render.progress_percent = 20
        render.updated_at = _utcnow()
        job.stage = render.stage
        job.updated_at = render.updated_at
        db.commit()
        logger.info("job_stage", extra={"job_id": job.id, "stage": "rendering"})

        result = render_lyric_video(
            input_audio_path=original_path(asset.storage_key),
            lyrics_text=None,  # Lyrics may be loaded from analysis in future
            lyrics_format="srt",
            output_path=None,
            mode="waveform",
        )

        now = _utcnow()
        render.status = "succeeded"
        render.stage = "completed"
        render.progress_percent = 100
        render.publish_status = "queued"  # Ready for publishing
        render.updated_at = now
        render.completed_at = now
        job.status = "succeeded"
        job.stage = "completed"
        job.finished_at = now
        job.updated_at = now
        logger.info("job_completed", extra={
            "job_id": job.id,
            "task_type": job.task_type,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - _render_start) * 1000),
        })
        db.commit()
    except LyricVideoError as exc:
        _fail_video_job(db, job, render, exc.code)
        db.commit()
    except Exception as exc:
        logger.error(f"lyric_video_job_error: {type(exc).__name__}: {exc}")
        _fail_video_job(db, job, render, "INTERNAL_ERROR")
        db.commit()


def _update_job_heartbeat(db: Session, job: AnalysisJob) -> None:
    """Update job's updated_at to prevent stale timeout."""
    try:
        job.updated_at = _utcnow()
        db.commit()
    except Exception as e:
        logger.warning(
            "job_heartbeat_failed",
            extra={"job_id": job.id, "error": str(e)[:100]},
        )
        db.rollback()


def _youtube_publish_job(db: Session, job: AnalysisJob) -> None:
    """Publish a rendered video to YouTube."""
    import sys
    print(f"[YOUTUBE_PUBLISH_START] Job {job.id[:8]}...", file=sys.stderr, flush=True)
    
    render = db.query(VideoRender).filter(
        VideoRender.id == job.subject_id,
        VideoRender.owner_id == job.owner_id,
    ).first()
    
    logger.info(
        "youtube_publish_job_starting",
        extra={"render_id": job.subject_id, "owner_id": job.owner_id},
    )
    
    if render is None or render.status != "succeeded":
        logger.warning(
            "youtube_publish_job_invalid_render",
            extra={
                "render_id": job.subject_id,
                "render_exists": render is not None,
                "render_status": render.status if render else None,
            },
        )
        _fail_video_job(db, job, render, "RESOURCE_NOT_FOUND")
        db.commit()
        return

    # Load YouTube OAuth token (check before changing render status)
    conn = db.query(PlatformConnection).filter(
        PlatformConnection.owner_id == job.owner_id,
        PlatformConnection.provider == "youtube",
        PlatformConnection.status == "connected",
    ).first()
    if conn is None or not conn.access_token_encrypted:
        logger.warning(
            "youtube_publish_job_no_connection",
            extra={
                "render_id": render.id,
                "connection_exists": conn is not None,
            },
        )
        render.status = "failed"
        render.publish_status = "failed"
        render.publish_error = "YouTube not connected"
        render.updated_at = _utcnow()
        render.completed_at = render.updated_at
        job.status = "failed"
        job.stage = "failed"
        job.error_code = "YT_NOT_CONNECTED"
        job.finished_at = render.updated_at
        job.updated_at = render.updated_at
        db.commit()
        logger.warning("job_failed", extra={"job_id": job.id, "error_code": "YT_NOT_CONNECTED"})
        return

    render.status = "running"
    render.stage = "preparing"
    render.progress_percent = 10
    render.publish_status = "publishing"
    render.updated_at = _utcnow()
    job.stage = render.stage
    job.updated_at = render.updated_at
    db.commit()

    _publish_start = time.monotonic()
    try:
        # Decrypt access token
        logger.info(
            "youtube_publish_decrypting_token",
            extra={"render_id": render.id},
        )
        try:
            access_token = decrypt_token(conn.access_token_encrypted)
        except Exception as dec_exc:
            logger.error(
                "youtube_publish_token_decryption_failed",
                extra={"render_id": render.id, "error": str(dec_exc)[:200]},
                exc_info=True,
            )
            raise YouTubePublishError(
                "YT_AUTH_FAILED",
                f"Failed to decrypt YouTube access token: {str(dec_exc)}",
                is_recoverable=False,
            )
        logger.info(
            "youtube_access_token_decrypted",
            extra={"render_id": render.id},
        )

        # Load song to get actual title and artist
        song = db.query(StudioSong).filter(
            StudioSong.id == render.song_id,
            StudioSong.owner_id == job.owner_id,
        ).first()
        if song is None:
            raise YouTubePublishError(
                "RESOURCE_NOT_FOUND",
                f"Song not found for render {render.id}",
                is_recoverable=False,
            )

        # Validate video file exists
        video_path = str(render_output_path(render.id))
        if not os.path.exists(video_path):
            logger.error(
                "youtube_publish_video_file_not_found",
                extra={"render_id": render.id, "video_path": video_path},
            )
            raise YouTubePublishError(
                "VIDEO_FILE_NOT_FOUND",
                f"Render output file not found at {video_path}",
                is_recoverable=False,
            )
        logger.info(
            "youtube_publish_video_file_validated",
            extra={"render_id": render.id, "video_path": video_path},
        )

        # Generate metadata via Ollama (with timeout/fallback)
        render.stage = "generating_metadata"
        render.progress_percent = 30
        render.updated_at = _utcnow()
        job.stage = render.stage
        job.updated_at = render.updated_at
        db.commit()

        try:
            logger.info(
                "youtube_publish_generating_metadata",
                extra={"render_id": render.id},
            )
            # Note: signal.alarm is Unix-only and silently ignored on Windows.
            # We use threading to provide cross-platform timeout, or fall back if unavailable.
            metadata = generate_metadata(
                song_title=song.title,
                artist_name=song.artist_name or conn.account_name or "Artist",
                duration_seconds=60,
                mood=None,
            )
        except (TimeoutError, Exception) as e:
            # Fallback if Ollama is unavailable, slow, or any other error
            logger.warning(
                "youtube_publish_metadata_generation_failed",
                extra={"render_id": render.id, "error": str(e)[:200]},
            )
            from ..domain.schemas import VideoMetadata
            metadata = VideoMetadata(
                title=f"{song.title} - Music Visualizer",
                description=f"Music visualizer for {song.title} by {song.artist_name or conn.account_name or 'Artist'}",
                tags=["music", "visualizer", song.title[:50]],
            )

        render.metadata_json = {
            "title": metadata.title,
            "description": metadata.description,
            "tags": metadata.tags,
        }
        logger.info(
            "youtube_publish_metadata_prepared",
            extra={
                "render_id": render.id,
                "video_title": metadata.title,
            },
        )

        # Upload to YouTube
        render.stage = "uploading"
        render.progress_percent = 60
        render.updated_at = _utcnow()
        job.stage = render.stage
        job.updated_at = render.updated_at
        db.commit()

        # Decrypt refresh token if available
        refresh_token = None
        if conn.refresh_token_encrypted:
            try:
                refresh_token = decrypt_token(conn.refresh_token_encrypted)
                logger.info(
                    "youtube_refresh_token_decrypted",
                    extra={"render_id": render.id},
                )
            except Exception as dec_exc:
                logger.warning(
                    "youtube_refresh_token_decryption_failed",
                    extra={"render_id": render.id, "error": str(dec_exc)[:200]},
                )
                # Continue without refresh token; upload may still work if access token is valid

        logger.info(
            "youtube_upload_starting",
            extra={
                "render_id": render.id,
                "video_title": metadata.title,
                "video_file_path": video_path,
                "has_refresh_token": refresh_token is not None,
            },
        )

        video = publish_to_youtube(
            access_token=access_token,
            refresh_token=refresh_token,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            is_public=False,
            video_file_path=video_path,
        )
        
        # Update job heartbeat to prevent stale timeout
        _update_job_heartbeat(db, job)

        # Update render with platform URL
        now = _utcnow()
        render.status = "succeeded"
        render.stage = "completed"
        render.progress_percent = 100
        render.publish_status = "published"
        platform_urls = render.platform_urls or {}
        platform_urls["youtube"] = video.url
        render.platform_urls = platform_urls
        render.updated_at = now
        render.completed_at = now
        job.status = "succeeded"
        job.stage = "completed"
        job.finished_at = now
        job.updated_at = now
        logger.info(
            "youtube_upload_completed",
            extra={
                "render_id": render.id,
                "video_id": video.video_id,
                "video_url": video.url,
            },
        )
        logger.info("job_completed", extra={
            "job_id": job.id,
            "task_type": job.task_type,
            "status": "succeeded",
            "duration_ms": round((time.monotonic() - _publish_start) * 1000),
        })
        db.commit()

    except YouTubePublishError as exc:
        now = _utcnow()
        render.status = "failed"
        render.publish_status = "failed"
        render.publish_error = exc.message
        render.updated_at = now
        render.completed_at = now
        
        # Use error classification to determine if job should be retried
        is_retryable = _classify_error(exc.code)
        job.status = "failed_retryable" if is_retryable else "failed"
        job.stage = "failed"
        job.error_code = exc.code
        job.finished_at = now
        job.updated_at = now
        db.commit()
        logger.warning(
            "youtube_upload_failed",
            extra={
                "render_id": render.id,
                "job_id": job.id,
                "error_code": exc.code,
                "error_message": exc.message,
                "retryable": is_retryable,
            },
        )
        if is_retryable:
            # Job will be retried by scheduler
            raise exc
    except Exception as exc:
        logger.error(
            "youtube_publish_job_error",
            extra={
                "render_id": render.id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            exc_info=True,
        )
        now = _utcnow()
        render.status = "failed"
        render.publish_status = "failed"
        render.publish_error = str(exc)
        render.updated_at = now
        render.completed_at = now
        job.status = "failed"
        job.stage = "failed"
        job.error_code = "INTERNAL_ERROR"
        job.finished_at = now
        job.updated_at = now
        db.commit()

