"""Versioned first-slice API: private songs, uploads, analysis, and reports."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import base64
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath, Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..core.auth import current_owner
from ..core.errors import ApiError
from ..core.rate_limiter import limiter
from ..database import Base, get_db
from ..domain.models import (
    AgentPipelineRun,
    AnalysisJob,
    AnalysisReport,
    ArtistWorkspaceProfile,
    ConsentRecord,
    IdempotencyRecord,
    MarketingCampaign,
    MediaAsset,
    PlatformConnection,
    PlatformOAuthState,
    ReleasePlan,
    RightsDeclaration,
    SongAnalysis,
    SongAnalysisLyrics,
    StudioSong,
    VideoRender,
    new_id,
)
from ..domain.schemas import (
    AgentPipelineOut,
    ARReportOut,
    AudienceHypothesesOut,
    MetadataGenerationRequest,
    MetadataGenerationResponse,
    ReleasePlanCreate,
    ReleasePlanListOut,
    ReleasePlanOut,
    ReleasePlanPatch,
    AnalysisAccepted,
    AnalysisRequest,
    AnalysisStatusOut,
    ConsentCreate,
    ConsentListOut,
    ConsentOut,
    ConsentWithdrawalOut,
    ArtistProfileOut,
    ArtistProfileUpsert,
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetListOut,
    AssetOut,
    JobOut,
    SafeError,
    SongCreate,
    SongIntelligenceOut,
    SongListOut,
    SongOut,
    SongPatch,
    RightsDeclarationCreate,
    RightsDeclarationListOut,
    RightsDeclarationOut,
    UploadIntentRequest,
    UploadIntentResponse,
    VideoRenderListOut,
    VideoRenderOut,
    VideoRenderRequest,
    YouTubePublishRequest,
    YouTubePublishResponse,
    CampaignCreate,
    CampaignPatch,
    CampaignOut,
    CampaignListOut,
)
from ..services.storage import asset_directory, original_path, render_output_path, write_upload
from ..services.job_runner import run_v1_job
from ..services.consent import has_active_consent
from ..services.lyrics import analyze_lyrics
from ..services.audience import build_audience_hypotheses
from ..services.release_planning import build_release_tasks
from ..services.video_rendering import build_scene_plan, renderer_capabilities
from ..services.platform_oauth import provider_is_configured
from ..services.ollama_provider import generate_metadata
from ..services.budget_calculator import allocate_budget
from ..services.campaign_planner import (
    check_ollama_available,
    generate_song_quality_report,
    generate_campaign_plan,
    generate_captions_and_concepts,
    generate_posting_schedule,
)
from ..engine.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["v1"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _song_response(song: StudioSong) -> SongOut:
    return SongOut(
        song_id=song.id,
        title=song.title,
        artist_name=song.artist_name,
        language=song.language,
        genre_preferences=song.genre_preferences or [],
        release_goal=song.release_goal,
        created_at=_utc(song.created_at),
        updated_at=_utc(song.updated_at),
    )


def _profile_response(profile: ArtistWorkspaceProfile) -> ArtistProfileOut:
    return ArtistProfileOut(
        profile_id=profile.id,
        display_name=profile.display_name,
        bio=profile.bio,
        primary_genre=profile.primary_genre,
        language=profile.language,
        territories=profile.territories or [],
        goals=profile.goals or [],
        brand_voice=profile.brand_voice,
        onboarding_completed_at=_utc(profile.onboarding_completed_at),
        updated_at=_utc(profile.updated_at),
    )


def _release_plan_response(plan: ReleasePlan) -> ReleasePlanOut:
    return ReleasePlanOut(
        plan_id=plan.id,
        song_id=plan.song_id,
        analysis_id=plan.analysis_id,
        release_date=plan.release_date,
        goal=plan.goal,
        status=plan.status,
        tasks=plan.tasks_json,
        limitations=[
            "This is a draft checklist, not a performance forecast.",
            "Tasks do not publish content, connect accounts, contact distributors, or spend money.",
            "No costs or reach estimates are available in this local planner.",
        ],
        created_at=_utc(plan.created_at),
        updated_at=_utc(plan.updated_at),
        approved_at=_utc(plan.approved_at),
    )


def _video_render_response(render: VideoRender) -> VideoRenderOut:
    is_ready = render.status == "succeeded"
    return VideoRenderOut(
        render_id=render.id,
        song_id=render.song_id,
        asset_id=render.asset_id,
        job_id=render.job_id,
        render_format=render.render_format,
        status=render.status,
        stage=render.stage,
        progress_percent=render.progress_percent,
        error=_error(render.error_code, None),
        scene_plan=render.scene_plan_json,
        provenance=render.provenance_json,
        output_metadata=render.output_metadata_json,
        output_size_bytes=render.output_size_bytes,
        created_at=_utc(render.created_at),
        updated_at=_utc(render.updated_at),
        completed_at=_utc(render.completed_at),
        status_url=f"/api/v1/video-renders/{render.id}",
        download_url=f"/api/v1/video-renders/{render.id}/download" if is_ready else None,
    )


def _consent_response(consent: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        consent_id=consent.id,
        consent_type=consent.consent_type,
        song_id=consent.song_id,
        granted=bool(consent.granted),
        withdraws_consent_id=consent.withdraws_consent_id,
        created_at=_utc(consent.created_at),
    )


def _rights_response(declaration: RightsDeclaration) -> RightsDeclarationOut:
    return RightsDeclarationOut(
        declaration_id=declaration.id,
        song_id=declaration.song_id,
        recording_rights_basis=declaration.recording_rights_basis,
        composition_rights_basis=declaration.composition_rights_basis,
        rights_confirmed=bool(declaration.rights_confirmed),
        created_at=_utc(declaration.created_at),
    )


def _latest_rights_declaration(
    db: Session,
    owner_id: str,
    song_id: str,
) -> RightsDeclaration | None:
    return (
        db.query(RightsDeclaration)
        .filter(
            RightsDeclaration.owner_id == owner_id,
            RightsDeclaration.song_id == song_id,
        )
        .order_by(RightsDeclaration.created_at.desc(), RightsDeclaration.id.desc())
        .first()
    )


def _require_audio_authorization(db: Session, owner_id: str, song_id: str) -> None:
    if _latest_rights_declaration(db, owner_id, song_id) is None:
        raise ApiError(
            403,
            "RIGHTS_DECLARATION_REQUIRED",
            "Declare your rights to this recording and composition before uploading audio.",
        )
    if not has_active_consent(db, owner_id, "audio_processing", song_id):
        raise ApiError(
            403,
            "CONSENT_REQUIRED",
            "Explicit consent for private audio processing is required.",
        )


def _require_analysis_authorization(db: Session, owner_id: str, song_id: str) -> None:
    _require_audio_authorization(db, owner_id, song_id)
    if not has_active_consent(db, owner_id, "derived_analysis_storage", song_id):
        raise ApiError(
            403,
            "CONSENT_REQUIRED",
            "Explicit consent to store derived analysis in the private workspace is required.",
        )


def _song_cursor(song: StudioSong) -> str:
    value = json.dumps({"created_at": _utc(song.created_at).isoformat(), "song_id": song.id})
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_song_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(cursor + padding))
        created_at = datetime.fromisoformat(value["created_at"])
        song_id = value["song_id"]
        if not isinstance(song_id, str) or not song_id:
            raise ValueError
        return _utc(created_at), song_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(422, "VALIDATION_ERROR", "The song cursor is invalid.") from exc


def _get_song(db: Session, song_id: str, owner_id: str) -> StudioSong:
    song = db.query(StudioSong).filter(
        StudioSong.id == song_id,
        StudioSong.owner_id == owner_id,
    ).first()
    if song is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Song was not found.")
    return song


def _get_analysis(db: Session, analysis_id: str, owner_id: str) -> SongAnalysis:
    analysis = db.query(SongAnalysis).filter(
        SongAnalysis.id == analysis_id,
        SongAnalysis.owner_id == owner_id,
    ).first()
    if analysis is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Analysis was not found.")
    return analysis


def _error(code: str | None, message: str | None) -> SafeError | None:
    if code is None:
        return None
    safe_messages = {
        "AUDIO_FILE_TOO_LARGE": "The audio file exceeds the configured size limit.",
        "AUDIO_DURATION_EXCEEDED": "The audio file exceeds the configured duration limit.",
        "AUDIO_FORMAT_UNSUPPORTED": "The uploaded audio format is not supported.",
        "AUDIO_FILE_CORRUPT": "The uploaded audio could not be decoded.",
        "AUDIO_ANALYZER_UNAVAILABLE": "The configured audio processing tools are unavailable.",
        "AUDIO_PROCESSING_FAILED": "Audio processing failed.",
        "AI_PROVIDER_UNAVAILABLE": "The report provider is unavailable.",
        "AI_OUTPUT_INVALID": "The report provider returned a response that failed validation.",
        "CONSENT_REQUIRED": "Required processing, analysis-storage, or provider consent is no longer active.",
        "RIGHTS_DECLARATION_REQUIRED": "A rights declaration is required before creating promotional media.",
        "RESOURCE_NOT_READY": "The requested resource is not ready yet.",
        "JOB_STATE_INVALID": "The prior render request is no longer available.",
        "VIDEO_NOT_READY": "The rendered MP4 is not ready for download.",
        "INTERNAL_ERROR": "The requested job failed unexpectedly.",
        "WORKER_INTERRUPTED": "The job was interrupted before completion.",
        "VIDEO_RENDERER_UNAVAILABLE": "Local video rendering requires FFmpeg with the drawtext and video encoder components.",
        "VIDEO_RENDER_FAILED": "FFmpeg could not render this video.",
        "VIDEO_RENDER_TIMEOUT": "The video render exceeded the local processing time limit.",
        "VIDEO_OUTPUT_INVALID": "The rendered file did not pass MP4 validation.",
        "VIDEO_SOURCE_UNAVAILABLE": "The authorized source audio is no longer available.",
        "VIDEO_OUTPUT_MISSING": "The private rendered file is not available.",
    }
    return SafeError(code=code, message=safe_messages.get(code, "The requested operation failed."))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(Base.metadata.tables["v1_songs"].select().limit(0))
    except Exception as exc:
        raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "The application is not ready.") from exc
    return {"status": "ready"}


@router.get("/capabilities")
def capabilities() -> dict:
    import importlib.util
    import httpx
    from pathlib import Path

    # Check FFmpeg availability - simple path check
    ffmpeg_path = Path(settings.ffmpeg_path)
    ffmpeg_available = ffmpeg_path.exists() and ffmpeg_path.is_file()
    
    # Check FFprobe availability - simple path check
    ffprobe_path = Path(settings.ffprobe_path)
    ffprobe_available = ffprobe_path.exists() and ffprobe_path.is_file()
    
    openrouter_available = bool(settings.openrouter_api_key and settings.openrouter_model)
    
    # Check Ollama availability
    ollama_available = False
    if settings.ollama_enabled:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{settings.ollama_base_url}/api/tags")
                ollama_available = response.status_code == 200
        except Exception:
            ollama_available = False
    
    # Check YouTube publishing availability
    youtube_publishing_available = provider_is_configured("youtube")
    
    video = renderer_capabilities()
    return {
        "api_version": "v1",
        "capabilities": {
            "song_upload": True,
            "audio_analysis": ffmpeg_available and ffprobe_available,
            "librosa_features": importlib.util.find_spec("librosa") is not None,
            "essentia_features": importlib.util.find_spec("essentia") is not None,
            "mock_ai_report": True,
            "openrouter_report": openrouter_available,
            "social_publishing": False,
            "music_distribution": False,
            "paid_campaign_execution": False,
            "music_visualizer_render": video["music_visualizer"],
            "full_music_video_render": video["full_music_video"],
            "youtube_connection": provider_is_configured("youtube"),
            "instagram_connection": provider_is_configured("facebook"),
            "facebook_connection": provider_is_configured("facebook"),
            "ollama_available": ollama_available,
            "youtube_publishing_available": youtube_publishing_available,
        },
    }


@router.get("/session")
@limiter.limit("10/minute")
def session_check(request: Request, owner_id: str = Depends(current_owner)) -> dict[str, bool]:
    return {"authenticated": bool(owner_id)}


@router.get("/artist/profile", response_model=ArtistProfileOut | None)
def get_artist_profile(
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ArtistProfileOut | None:
    profile = db.query(ArtistWorkspaceProfile).filter(
        ArtistWorkspaceProfile.owner_id == owner_id
    ).first()
    return _profile_response(profile) if profile else None


@router.put("/artist/profile", response_model=ArtistProfileOut)
def upsert_artist_profile(
    payload: ArtistProfileUpsert,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ArtistProfileOut:
    profile = db.query(ArtistWorkspaceProfile).filter(
        ArtistWorkspaceProfile.owner_id == owner_id
    ).first()
    values = payload.model_dump()
    if profile is None:
        profile = ArtistWorkspaceProfile(owner_id=owner_id, **values)
        db.add(profile)
    else:
        for name, value in values.items():
            setattr(profile, name, value)
        profile.updated_at = _utcnow()
    db.commit()
    db.refresh(profile)
    return _profile_response(profile)


@router.get("/consents", response_model=ConsentListOut)
def list_consents(
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ConsentListOut:
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.owner_id == owner_id)
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .all()
    )
    return ConsentListOut(items=[_consent_response(row) for row in rows])


@router.post("/consents", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_consent(
    request: Request,
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ConsentOut:
    if payload.consent_type == "platform_account_connection" and payload.song_id is not None:
        raise ApiError(422, "VALIDATION_ERROR", "Platform-account connection consent must apply to the workspace.")
    if payload.song_id is not None:
        _get_song(db, payload.song_id, owner_id)
    if has_active_consent(db, owner_id, payload.consent_type, payload.song_id):
        raise ApiError(409, "CONSENT_ALREADY_ACTIVE", "This consent is already active for the requested scope.")
    consent = ConsentRecord(
        owner_id=owner_id,
        consent_type=payload.consent_type,
        song_id=payload.song_id,
        granted=True,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    logger.info("consent_granted", extra={
        "owner_id": owner_id,
        "consent_type": payload.consent_type,
        "song_id": payload.song_id,
    })
    return _consent_response(consent)


@router.post("/consents/{consent_id}/withdraw", response_model=ConsentWithdrawalOut)
@limiter.limit("10/minute")
def withdraw_consent(
    request: Request,
    consent_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ConsentWithdrawalOut:
    consent = db.query(ConsentRecord).filter(
        ConsentRecord.id == consent_id,
        ConsentRecord.owner_id == owner_id,
        ConsentRecord.granted.is_(True),
    ).first()
    if consent is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Active consent was not found.")
    if not has_active_consent(db, owner_id, consent.consent_type, consent.song_id):
        raise ApiError(409, "CONSENT_NOT_ACTIVE", "This consent is no longer active.")
    withdrawal = ConsentRecord(
        owner_id=owner_id,
        consent_type=consent.consent_type,
        song_id=consent.song_id,
        granted=False,
        withdraws_consent_id=consent.id,
    )
    db.add(withdrawal)
    if consent.consent_type == "platform_account_connection" and consent.song_id is None:
        db.query(PlatformConnection).filter(
            PlatformConnection.owner_id == owner_id,
        ).update(
            {
                PlatformConnection.account_id: None,
                PlatformConnection.account_name: None,
                PlatformConnection.access_token_encrypted: None,
                PlatformConnection.refresh_token_encrypted: None,
                PlatformConnection.granted_scopes_json: [],
                PlatformConnection.access_token_expires_at: None,
                PlatformConnection.status: "disconnected",
                PlatformConnection.disconnected_at: _utcnow(),
                PlatformConnection.updated_at: _utcnow(),
            },
            synchronize_session=False,
        )
        db.query(PlatformOAuthState).filter(
            PlatformOAuthState.owner_id == owner_id,
            PlatformOAuthState.consumed_at.is_(None),
        ).update(
            {PlatformOAuthState.consumed_at: _utcnow()},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(withdrawal)
    logger.warning("consent_withdrawn", extra={
        "owner_id": owner_id,
        "consent_type": consent.consent_type,
        "song_id": consent.song_id,
    })
    return ConsentWithdrawalOut(**_consent_response(withdrawal).model_dump())


@router.get("/rights/declarations", response_model=RightsDeclarationListOut)
def list_rights_declarations(
    song_id: str | None = None,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> RightsDeclarationListOut:
    query = db.query(RightsDeclaration).filter(RightsDeclaration.owner_id == owner_id)
    if song_id is not None:
        _get_song(db, song_id, owner_id)
        query = query.filter(RightsDeclaration.song_id == song_id)
    rows = query.order_by(RightsDeclaration.created_at.desc(), RightsDeclaration.id.desc()).all()
    return RightsDeclarationListOut(items=[_rights_response(row) for row in rows])


@router.post(
    "/rights/declarations",
    response_model=RightsDeclarationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_rights_declaration(
    payload: RightsDeclarationCreate,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> RightsDeclarationOut:
    _get_song(db, payload.song_id, owner_id)
    declaration = RightsDeclaration(
        owner_id=owner_id,
        song_id=payload.song_id,
        recording_rights_basis=payload.recording_rights_basis,
        composition_rights_basis=payload.composition_rights_basis,
        rights_confirmed=payload.rights_confirmed,
    )
    db.add(declaration)
    db.commit()
    db.refresh(declaration)
    return _rights_response(declaration)


@router.get("/songs", response_model=SongListOut)
def list_songs(
    limit: int = 10,
    cursor: str | None = None,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> SongListOut:
    if not 1 <= limit <= 50:
        raise ApiError(422, "VALIDATION_ERROR", "Song page size must be between 1 and 50.")
    query = db.query(StudioSong).filter(StudioSong.owner_id == owner_id)
    if cursor:
        created_at, song_id = _decode_song_cursor(cursor)
        query = query.filter(
            or_(
                StudioSong.created_at < created_at,
                and_(StudioSong.created_at == created_at, StudioSong.id < song_id),
            )
        )
    songs = query.order_by(desc(StudioSong.created_at), desc(StudioSong.id)).limit(limit + 1).all()
    has_more = len(songs) > limit
    items = songs[:limit]
    return SongListOut(
        items=[_song_response(song) for song in items],
        next_cursor=_song_cursor(items[-1]) if has_more and items else None,
        total_count=db.query(StudioSong).filter(StudioSong.owner_id == owner_id).count(),
    )


@router.post("/songs", response_model=SongOut, status_code=status.HTTP_201_CREATED)
def create_song(
    payload: SongCreate,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> SongOut:
    values = payload.model_dump()
    profile = db.query(ArtistWorkspaceProfile).filter(
        ArtistWorkspaceProfile.owner_id == owner_id
    ).first()
    if profile:
        values["artist_name"] = values["artist_name"] or profile.display_name
        values["language"] = values["language"] or profile.language
        values["genre_preferences"] = values["genre_preferences"] or (
            [profile.primary_genre] if profile.primary_genre else []
        )
    song = StudioSong(owner_id=owner_id, **values)
    db.add(song)
    db.commit()
    db.refresh(song)
    return _song_response(song)


@router.get("/songs/{song_id}", response_model=SongOut)
def get_song(
    song_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> SongOut:
    return _song_response(_get_song(db, song_id, owner_id))


@router.patch("/songs/{song_id}", response_model=SongOut)
def patch_song(
    song_id: str,
    payload: SongPatch,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> SongOut:
    song = _get_song(db, song_id, owner_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError(422, "VALIDATION_ERROR", "Provide at least one song field to update.")
    for name, value in changes.items():
        setattr(song, name, value)
    song.updated_at = _utcnow()
    db.commit()
    db.refresh(song)
    return _song_response(song)


@router.post(
    "/songs/{song_id}/assets/upload-intent",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/hour")
def create_upload_intent(
    request: Request,
    song_id: str,
    payload: UploadIntentRequest,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> UploadIntentResponse:
    _get_song(db, song_id, owner_id)
    _require_audio_authorization(db, owner_id, song_id)
    if payload.size_bytes > settings.max_upload_bytes:
        raise ApiError(413, "AUDIO_FILE_TOO_LARGE", "The audio file exceeds the configured size limit.")
    content_type = payload.declared_content_type
    if content_type and not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        raise ApiError(415, "AUDIO_FORMAT_UNSUPPORTED", "Upload an audio file.")
    filename = PurePosixPath(payload.filename.replace("\\", "/")).name
    if not filename or filename in {".", ".."}:
        raise ApiError(422, "VALIDATION_ERROR", "A valid filename is required.")
    asset = MediaAsset(
        song_id=song_id,
        owner_id=owner_id,
        filename=filename,
        declared_content_type=content_type,
        storage_key=new_id(),
        expected_size_bytes=payload.size_bytes,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    logger.info("song_upload_initiated", extra={
        "owner_id": owner_id,
        "song_id": song_id,
        "asset_id": asset.id,
        "file_size_mb": payload.size_bytes / (1024 * 1024),
    })
    upload_url = str(request.url_for("upload_asset", asset_id=asset.id))
    return UploadIntentResponse(
        asset_id=asset.id,
        upload_method="PUT",
        upload_url=upload_url,
        required_headers={"Authorization": "Bearer <token>"},
        expires_at=_utc(asset.expires_at),
    )


@router.put("/assets/{asset_id}/upload", name="upload_asset")
async def upload_asset(
    asset_id: str,
    request: Request,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> Response:
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.owner_id == owner_id,
    ).first()
    if asset is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset was not found.")
    _require_audio_authorization(db, owner_id, asset.song_id)
    if asset.status != "pending_upload" or _utc(asset.expires_at) < _utcnow():
        raise ApiError(409, "ASSET_NOT_READY", "The upload intent has expired or is no longer available.")
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_upload_bytes:
                raise ApiError(413, "AUDIO_FILE_TOO_LARGE", "The audio file exceeds the configured size limit.")
        except ValueError as exc:
            raise ApiError(400, "VALIDATION_ERROR", "Invalid content length.") from exc
    claimed = db.query(MediaAsset).filter(
        MediaAsset.id == asset.id,
        MediaAsset.owner_id == owner_id,
        MediaAsset.status == "pending_upload",
    ).update({"status": "uploading"}, synchronize_session=False)
    if claimed != 1:
        db.rollback()
        raise ApiError(409, "ASSET_NOT_READY", "This upload intent is already being used.")
    db.commit()
    try:
        size_bytes, checksum = await write_upload(request, asset.storage_key, asset.expected_size_bytes)
    except Exception:
        db.rollback()
        asset = db.query(MediaAsset).filter(
            MediaAsset.id == asset_id,
            MediaAsset.owner_id == owner_id,
            MediaAsset.status == "uploading",
        ).first()
        if asset is not None:
            asset.status = "pending_upload"
            db.commit()
        raise
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.owner_id == owner_id,
    ).first()
    if asset is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset was not found.")
    asset.size_bytes = size_bytes
    asset.checksum_sha256 = checksum
    asset.status = "uploaded"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/songs/{song_id}/assets/complete",
    response_model=AssetCompleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def complete_upload(
    song_id: str,
    payload: AssetCompleteRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AssetCompleteResponse:
    _get_song(db, song_id, owner_id)
    _require_audio_authorization(db, owner_id, song_id)
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == payload.asset_id,
        MediaAsset.song_id == song_id,
        MediaAsset.owner_id == owner_id,
    ).first()
    if asset is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset was not found.")
    if asset.status in {"verifying", "ready"}:
        existing_job = db.query(AnalysisJob).filter(
            AnalysisJob.task_type == "asset_verification",
            AnalysisJob.subject_id == asset.id,
            AnalysisJob.owner_id == owner_id,
        ).order_by(AnalysisJob.created_at.desc()).first()
        if existing_job is not None:
            return AssetCompleteResponse(
                asset_id=asset.id,
                status=asset.status,
                job_id=existing_job.id,
                status_url=f"/api/v1/jobs/{existing_job.id}",
            )
    if asset.status != "uploaded" or not original_path(asset.storage_key).is_file():
        raise ApiError(409, "ASSET_NOT_READY", "The uploaded asset is not available for verification.")
    job = AnalysisJob(owner_id=owner_id, task_type="asset_verification", subject_id=asset.id)
    db.add(job)
    asset.status = "verifying"
    db.commit()
    db.refresh(job)
    background.add_task(run_v1_job, job.id)
    return AssetCompleteResponse(
        asset_id=asset.id,
        status="verifying",
        job_id=job.id,
        status_url=f"/api/v1/jobs/{job.id}",
    )


@router.get("/songs/{song_id}/assets", response_model=AssetListOut)
def list_assets(
    song_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AssetListOut:
    _get_song(db, song_id, owner_id)
    rows = db.query(MediaAsset).filter(
        MediaAsset.song_id == song_id,
        MediaAsset.owner_id == owner_id,
    ).order_by(MediaAsset.created_at.desc()).limit(100).all()
    return AssetListOut(
        items=[
            AssetOut(
                asset_id=row.id,
                asset_kind=row.asset_kind,
                status=row.status,
                size_bytes=row.size_bytes,
                checksum_sha256=row.checksum_sha256,
                created_at=_utc(row.created_at),
            )
            for row in rows
        ]
    )


@router.post(
    "/songs/{song_id}/analyses",
    response_model=AnalysisAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
def create_analysis(
    request: Request,
    song_id: str,
    payload: AnalysisRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> AnalysisAccepted:
    _get_song(db, song_id, owner_id)
    _require_analysis_authorization(db, owner_id, song_id)
    if payload.allow_third_party_ai and not has_active_consent(
        db,
        owner_id,
        "third_party_ai",
        song_id,
    ):
        raise ApiError(
            403,
            "CONSENT_REQUIRED",
            "Explicit consent to send structured analysis data to a third-party AI provider is required.",
        )
    if payload.lyrics_asset_id is not None:
        raise ApiError(422, "VALIDATION_ERROR", "Lyrics assets are not implemented in this milestone.")
    if payload.include_pretrained_predictions:
        raise ApiError(422, "VALIDATION_ERROR", "No reviewed pretrained prediction model is configured.")
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == payload.asset_id,
        MediaAsset.song_id == song_id,
        MediaAsset.owner_id == owner_id,
    ).first()
    if asset is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Asset was not found.")
    if asset.status != "ready":
        raise ApiError(409, "ASSET_NOT_READY", "The audio asset must be verified before analysis.")

    operation = f"song-analysis:{song_id}"
    request_hash = hashlib.sha256(
        json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    prior = db.query(IdempotencyRecord).filter(
        IdempotencyRecord.owner_id == owner_id,
        IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used with a different request.")
        response_data = dict(prior.response_json)
        response_data["requested_at"] = datetime.fromisoformat(response_data["requested_at"])
        return AnalysisAccepted.model_validate(response_data)

    running = db.query(SongAnalysis).filter(
        SongAnalysis.song_id == song_id,
        SongAnalysis.asset_id == asset.id,
        SongAnalysis.owner_id == owner_id,
        SongAnalysis.status.in_(["queued", "running"]),
    ).first()
    if running:
        raise ApiError(409, "ANALYSIS_ALREADY_RUNNING", "An analysis is already running for this asset.")

    job = AnalysisJob(owner_id=owner_id, task_type="song_analysis")
    db.add(job)
    db.flush()
    analysis = SongAnalysis(
        song_id=song_id,
        asset_id=asset.id,
        owner_id=owner_id,
        job_id=job.id,
        analysis_version=payload.analysis_profile,
    )
    db.add(analysis)
    db.flush()
    if payload.lyrics and payload.lyrics.strip():
        db.add(
            SongAnalysisLyrics(
                analysis_id=analysis.id,
                analysis_json=analyze_lyrics(payload.lyrics),
            )
        )
    job.subject_id = analysis.id
    accepted = AnalysisAccepted(
        analysis_id=analysis.id,
        job_id=job.id,
        status="queued",
        status_url=f"/api/v1/analyses/{analysis.id}",
        requested_at=_utc(analysis.created_at),
    )
    db.add(
        IdempotencyRecord(
            owner_id=owner_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_json=accepted.model_dump(mode="json"),
        )
    )
    db.commit()
    logger.info("analysis_job_created", extra={
        "owner_id": owner_id,
        "song_id": song_id,
        "analysis_id": analysis.id,
        "job_id": job.id,
    })
    background.add_task(
        run_v1_job,
        job.id,
        payload.generate_ai_report,
        payload.allow_third_party_ai,
    )
    return accepted


@router.get("/analyses/{analysis_id}", response_model=AnalysisStatusOut)
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AnalysisStatusOut:
    analysis = _get_analysis(db, analysis_id, owner_id)
    return AnalysisStatusOut(
        analysis_id=analysis.id,
        song_id=analysis.song_id,
        status=analysis.status,
        stage=analysis.stage,
        progress_percent=analysis.progress_percent,
        created_at=_utc(analysis.created_at),
        updated_at=_utc(analysis.updated_at),
        error=_error(analysis.error_code, None),
    )


@router.get("/analyses/{analysis_id}/intelligence", response_model=SongIntelligenceOut)
def get_intelligence(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> SongIntelligenceOut:
    analysis = _get_analysis(db, analysis_id, owner_id)
    if analysis.intelligence_json is None:
        raise ApiError(409, "ANALYSIS_NOT_COMPLETE", "Song Intelligence is not available yet.")
    return SongIntelligenceOut(
        analysis_id=analysis.id,
        song_id=analysis.song_id,
        schema_version=analysis.schema_version,
        analysis_version=analysis.analysis_version,
        created_at=_utc(analysis.updated_at),
        **analysis.intelligence_json,
    )


def _agent_pipeline_response(record: AgentPipelineRun) -> AgentPipelineOut:
    analysis = record.analysis
    return AgentPipelineOut(
        analysis_id=record.analysis_id,
        song_id=analysis.song_id,
        generated_at=_utc(record.created_at),
        results=record.results_json,
        limitations=[
            "This is a deterministic legacy pipeline, not an autonomous AI system.",
            "Audience segments are generic heuristic matches, not verified listener demographics.",
            "Energy and valence use genre defaults because the current audio analysis does not measure those subjective qualities.",
            "Campaign performance figures are simulated and are not predictions or real platform results.",
            "Suggested marketing activities, platforms, and budget percentages are drafts only; nothing is published, purchased, or executed.",
        ],
    )


def _agent_pipeline_numeric_feature(
    audio_features: dict[str, Any],
    names: tuple[str, ...],
) -> float | None:
    for name in names:
        feature = audio_features.get(name)
        if not isinstance(feature, dict) or feature.get("status") not in {"measured", "estimated"}:
            continue
        value = feature.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        return float(value)
    return None


@router.get("/analyses/{analysis_id}/agent-pipeline", response_model=AgentPipelineOut | None)
def get_agent_pipeline(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AgentPipelineOut | None:
    analysis = _get_analysis(db, analysis_id, owner_id)
    record = db.query(AgentPipelineRun).filter(
        AgentPipelineRun.analysis_id == analysis.id,
        AgentPipelineRun.owner_id == owner_id,
    ).first()
    return _agent_pipeline_response(record) if record is not None else None


@router.post("/analyses/{analysis_id}/agent-pipeline", response_model=AgentPipelineOut)
def run_agent_pipeline(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AgentPipelineOut:
    analysis = _get_analysis(db, analysis_id, owner_id)
    if analysis.status != "succeeded" or analysis.intelligence_json is None:
        raise ApiError(409, "ANALYSIS_NOT_COMPLETE", "Complete the song analysis before running the agent pipeline.")
    _require_analysis_authorization(db, owner_id, analysis.song_id)
    song = _get_song(db, analysis.song_id, owner_id)
    audio_features = analysis.intelligence_json.get("audio_features", {})
    if not isinstance(audio_features, dict):
        audio_features = {}
    lyrics_analysis = analysis.intelligence_json.get("lyrics_analysis", {})
    candidate_lines = lyrics_analysis.get("candidate_lines", []) if isinstance(lyrics_analysis, dict) else []
    derived_lyrics = "\n".join(
        item["text"]
        for item in candidate_lines
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    )
    profile = db.query(ArtistWorkspaceProfile).filter(
        ArtistWorkspaceProfile.owner_id == owner_id
    ).first()
    genres = song.genre_preferences or []
    genre = genres[0] if genres else (profile.primary_genre if profile and profile.primary_genre else "")
    artist = song.artist_name or (profile.display_name if profile else "Independent artist")
    key_feature = audio_features.get("musical_key")
    musical_key = None
    if (
        isinstance(key_feature, dict)
        and key_feature.get("status") in {"measured", "estimated"}
        and isinstance(key_feature.get("value"), str)
    ):
        musical_key = key_feature["value"]
    results = run_pipeline(
        {
            "title": song.title,
            "artist": artist,
            "genre": genre,
            "lyrics": derived_lyrics,
            "bpm": _agent_pipeline_numeric_feature(
                audio_features,
                ("tempo_bpm", "essentia_tempo_bpm"),
            ),
            "musical_key": musical_key,
        }
    )
    record = db.query(AgentPipelineRun).filter(
        AgentPipelineRun.analysis_id == analysis.id,
        AgentPipelineRun.owner_id == owner_id,
    ).first()
    if record is None:
        record = AgentPipelineRun(
            analysis_id=analysis.id,
            owner_id=owner_id,
            results_json=results,
        )
        db.add(record)
    else:
        record.results_json = results
        record.created_at = _utcnow()
    db.commit()
    db.refresh(record)
    return _agent_pipeline_response(record)


@router.get("/analyses/{analysis_id}/audience-hypotheses", response_model=AudienceHypothesesOut)
def get_audience_hypotheses(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> AudienceHypothesesOut:
    analysis = _get_analysis(db, analysis_id, owner_id)
    if analysis.intelligence_json is None:
        raise ApiError(409, "ANALYSIS_NOT_COMPLETE", "Song Intelligence is not available yet.")
    profile = db.query(ArtistWorkspaceProfile).filter(
        ArtistWorkspaceProfile.owner_id == owner_id
    ).first()
    return build_audience_hypotheses(
        analysis.id,
        analysis.intelligence_json,
        analysis.song,
        profile,
    )


@router.get("/songs/{song_id}/release-plans", response_model=ReleasePlanListOut)
def list_release_plans(
    song_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ReleasePlanListOut:
    _get_song(db, song_id, owner_id)
    plans = db.query(ReleasePlan).filter(
        ReleasePlan.song_id == song_id,
        ReleasePlan.owner_id == owner_id,
    ).order_by(desc(ReleasePlan.created_at), desc(ReleasePlan.id)).limit(limit).all()
    return ReleasePlanListOut(items=[_release_plan_response(plan) for plan in plans])


@router.post(
    "/release-plans",
    response_model=ReleasePlanOut,
    status_code=status.HTTP_201_CREATED,
)
def create_release_plan(
    payload: ReleasePlanCreate,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> ReleasePlanOut:
    _get_song(db, payload.song_id, owner_id)
    if payload.analysis_id is not None:
        analysis = _get_analysis(db, payload.analysis_id, owner_id)
        if analysis.song_id != payload.song_id or analysis.status != "succeeded":
            raise ApiError(409, "ANALYSIS_NOT_COMPLETE", "A completed analysis for this song is required.")

    operation = f"release-plan:create:{payload.song_id}"
    request_hash = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    prior = db.query(IdempotencyRecord).filter(
        IdempotencyRecord.owner_id == owner_id,
        IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == idempotency_key,
    ).first()
    if prior:
        if prior.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used with a different request.")
        return ReleasePlanOut.model_validate(prior.response_json)

    plan = ReleasePlan(
        owner_id=owner_id,
        song_id=payload.song_id,
        analysis_id=payload.analysis_id,
        release_date=payload.release_date,
        goal=payload.goal.strip() if payload.goal and payload.goal.strip() else None,
        tasks_json=build_release_tasks(payload.release_date),
    )
    db.add(plan)
    db.flush()
    response = _release_plan_response(plan)
    db.add(
        IdempotencyRecord(
            owner_id=owner_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_json=response.model_dump(mode="json"),
        )
    )
    db.commit()
    return response


@router.get("/release-plans/{plan_id}", response_model=ReleasePlanOut)
def get_release_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ReleasePlanOut:
    plan = db.query(ReleasePlan).filter(
        ReleasePlan.id == plan_id,
        ReleasePlan.owner_id == owner_id,
    ).first()
    if plan is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Release plan was not found.")
    return _release_plan_response(plan)


@router.patch("/release-plans/{plan_id}", response_model=ReleasePlanOut)
def update_release_plan(
    plan_id: str,
    payload: ReleasePlanPatch,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ReleasePlanOut:
    plan = db.query(ReleasePlan).filter(
        ReleasePlan.id == plan_id,
        ReleasePlan.owner_id == owner_id,
    ).first()
    if plan is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Release plan was not found.")
    if plan.status != "draft":
        raise ApiError(409, "RELEASE_PLAN_LOCKED", "Approved plans cannot be edited.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise ApiError(422, "VALIDATION_ERROR", "At least one release-plan field must be supplied.")
    if "release_date" in updates:
        plan.release_date = updates["release_date"]
    if "goal" in updates:
        goal = updates["goal"]
        plan.goal = goal.strip() if goal and goal.strip() else None
    plan.tasks_json = build_release_tasks(plan.release_date)
    db.commit()
    return _release_plan_response(plan)


@router.post("/release-plans/{plan_id}/approve", response_model=ReleasePlanOut)
def approve_release_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ReleasePlanOut:
    plan = db.query(ReleasePlan).filter(
        ReleasePlan.id == plan_id,
        ReleasePlan.owner_id == owner_id,
    ).first()
    if plan is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Release plan was not found.")
    if plan.status == "draft":
        plan.status = "approved"
        plan.approved_at = _utcnow()
        db.commit()
    return _release_plan_response(plan)


@router.get("/songs/{song_id}/video-renders", response_model=VideoRenderListOut)
def list_video_renders(
    song_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> VideoRenderListOut:
    _get_song(db, song_id, owner_id)
    renders = (
        db.query(VideoRender)
        .filter(VideoRender.song_id == song_id, VideoRender.owner_id == owner_id)
        .order_by(desc(VideoRender.created_at), desc(VideoRender.id))
        .limit(limit)
        .all()
    )
    return VideoRenderListOut(items=[_video_render_response(render) for render in renders])


@router.post(
    "/songs/{song_id}/video-renders",
    response_model=VideoRenderOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_video_render(
    song_id: str,
    payload: VideoRenderRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> VideoRenderOut:
    song = _get_song(db, song_id, owner_id)
    if not _latest_rights_declaration(db, owner_id, song_id):
        raise ApiError(
            403,
            "RIGHTS_DECLARATION_REQUIRED",
            "A current rights declaration is required to create promotional media.",
        )
    if not has_active_consent(db, owner_id, "audio_processing", song_id) or not has_active_consent(
        db,
        owner_id,
        "promotional_asset_generation",
        song_id,
    ):
        raise ApiError(403, "CONSENT_REQUIRED", "Audio-processing and promotional-media consent are required.")
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == payload.asset_id,
        MediaAsset.song_id == song_id,
        MediaAsset.owner_id == owner_id,
        MediaAsset.asset_kind == "audio_original",
        MediaAsset.status == "ready",
    ).first()
    if asset is None or asset.duration_seconds is None:
        raise ApiError(409, "RESOURCE_NOT_READY", "A verified original audio asset is required.")
    if not renderer_capabilities().get(payload.render_format, False):
        raise ApiError(503, "VIDEO_RENDERER_UNAVAILABLE", "The local FFmpeg video renderer is unavailable.")

    operation = f"video-render:create:{song_id}"
    request_hash = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    prior = db.query(IdempotencyRecord).filter(
        IdempotencyRecord.owner_id == owner_id,
        IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == idempotency_key,
    ).first()
    if prior is not None:
        if prior.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used with a different request.")
        prior_render_id = prior.response_json.get("render_id")
        prior_render = db.query(VideoRender).filter(
            VideoRender.id == prior_render_id,
            VideoRender.owner_id == owner_id,
        ).first()
        if prior_render is None:
            raise ApiError(409, "JOB_STATE_INVALID", "The prior render request is no longer available.")
        return _video_render_response(prior_render)

    render_id = new_id()
    job = AnalysisJob(
        owner_id=owner_id,
        task_type="video_render",
        subject_id=render_id,
    )
    db.add(job)
    db.flush()
    scene_plan = build_scene_plan(asset.duration_seconds, payload.render_format)
    render = VideoRender(
        id=render_id,
        owner_id=owner_id,
        song_id=song.id,
        asset_id=asset.id,
        job_id=job.id,
        render_format=payload.render_format,
        status="queued",
        stage="queued",
        progress_percent=0,
        render_settings_json={
            "renderer": "local_ffmpeg_motion_graphics",
            "resolution": "1280x720",
            "frame_rate": 30,
            "video_codec": "h264",
            "audio_codec": "aac",
            "uses_uploaded_artwork": False,
            "uses_ai_generated_footage": False,
        },
        scene_plan_json=scene_plan,
        provenance_json={
            "source_asset_id": asset.id,
            "source_sha256": asset.checksum_sha256,
            "visual_generation": "deterministic local FFmpeg waveform or spectrum graphics",
            "model": None,
            "artwork": "not used",
            "publishing": "not performed",
        },
    )
    db.add(render)
    db.add(
        IdempotencyRecord(
            owner_id=owner_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_json={"render_id": render.id},
        )
    )
    db.commit()
    db.refresh(render)
    background.add_task(run_v1_job, job.id)
    return _video_render_response(render)


@router.get("/video-renders/{render_id}", response_model=VideoRenderOut)
def get_video_render(
    render_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> VideoRenderOut:
    render = db.query(VideoRender).filter(
        VideoRender.id == render_id,
        VideoRender.owner_id == owner_id,
    ).first()
    if render is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Video render was not found.")
    return _video_render_response(render)


@router.get("/video-renders/{render_id}/download")
def download_video_render(
    render_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> FileResponse:
    render = db.query(VideoRender).filter(
        VideoRender.id == render_id,
        VideoRender.owner_id == owner_id,
    ).first()
    if render is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Video render was not found.")
    if render.status != "succeeded":
        raise ApiError(409, "VIDEO_NOT_READY", "The rendered MP4 is not ready for download.")
    path = render_output_path(render.id)
    if not path.is_file():
        raise ApiError(404, "VIDEO_OUTPUT_MISSING", "The private rendered file is not available.")
    song = _get_song(db, render.song_id, owner_id)
    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "-", song.title).strip("-_")[:80] or "song"
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{safe_title}-{render.render_format}.mp4",
        headers={"Cache-Control": "private, no-store"},
    )




@router.post("/video/{render_id}/generate-lyric-video", response_model=JobOut)
@limiter.limit("20/hour")
def generate_lyric_video(
    render_id: str,
    request: Request,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> JobOut:
    """Queue a lyric video generation job for a rendered video."""
    render = db.query(VideoRender).filter(
        VideoRender.id == render_id,
        VideoRender.owner_id == owner_id,
    ).first()
    if render is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Video render was not found.")
    
    # Create job
    job = AnalysisJob(
        id=new_id(),
        owner_id=owner_id,
        task_type="lyric_video_render",
        subject_id=render_id,
        status="queued",
        stage="queued",
    )
    db.add(job)
    db.commit()
    
    return JobOut(
        job_id=job.id,
        task_type=job.task_type,
        status=job.status,
        stage=job.stage,
        attempt=job.attempt,
        created_at=_utc(job.created_at),
        updated_at=_utc(job.updated_at),
        started_at=None,
        finished_at=None,
        error=None,
    )


@router.post("/video/{render_id}/publish-youtube", response_model=JobOut)
@limiter.limit("50/hour")
def publish_youtube(
    render_id: str,
    request: Request,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> JobOut:
    """Queue a YouTube publishing job for a rendered video."""
    render = db.query(VideoRender).filter(
        VideoRender.id == render_id,
        VideoRender.owner_id == owner_id,
    ).first()
    if render is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Video render was not found.")
    
    if render.status != "succeeded":
        raise ApiError(409, "VIDEO_NOT_READY", "Video must be succeeded status before publishing.")
    
    # Check YouTube token
    conn = db.query(PlatformConnection).filter(
        PlatformConnection.owner_id == owner_id,
        PlatformConnection.provider == "youtube",
        PlatformConnection.status == "connected",
    ).first()
    if conn is None:
        raise ApiError(403, "YT_NOT_CONNECTED", "YouTube account is not connected.")
    
    # Create job
    job = AnalysisJob(
        id=new_id(),
        owner_id=owner_id,
        task_type="youtube_publish",
        subject_id=render_id,
        status="queued",
        stage="queued",
    )
    db.add(job)
    db.commit()
    
    return JobOut(
        job_id=job.id,
        task_type=job.task_type,
        status=job.status,
        stage=job.stage,
        attempt=job.attempt,
        created_at=_utc(job.created_at),
        updated_at=_utc(job.updated_at),
        started_at=None,
        finished_at=None,
        error=None,
    )


@router.get("/analyses/{analysis_id}/report", response_model=ARReportOut)
def get_report(
    analysis_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> ARReportOut:
    analysis = _get_analysis(db, analysis_id, owner_id)
    report = db.query(AnalysisReport).filter(AnalysisReport.analysis_id == analysis.id).first()
    if report is None:
        raise ApiError(404, "REPORT_NOT_AVAILABLE", "The A&R report is not available yet.")
    return ARReportOut(
        report_id=report.id,
        analysis_id=analysis.id,
        schema_version=analysis.schema_version,
        provider=report.provider,
        model=report.model,
        prompt_version=report.prompt_version,
        created_at=report.created_at,
        **report.payload,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> JobOut:
    job = db.query(AnalysisJob).filter(
        AnalysisJob.id == job_id,
        AnalysisJob.owner_id == owner_id,
    ).first()
    if job is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Job was not found.")
    return JobOut(
        job_id=job.id,
        task_type=job.task_type,
        status=job.status,
        stage=job.stage,
        attempt=job.attempt,
        created_at=_utc(job.created_at),
        updated_at=_utc(job.updated_at),
        started_at=_utc(job.started_at),
        finished_at=_utc(job.finished_at),
        error=_error(job.error_code, None),
    )


@router.get("/video/genres", response_model=dict[str, Any])
def list_supported_genres() -> dict[str, Any]:
    """Return all supported genres with their configurations."""
    from ..services.genre_visualizer import get_all_genres, get_genre_with_config
    
    genres = get_all_genres()
    configs = {genre: get_genre_with_config(genre) for genre in genres}
    return {
        "total_genres": len(genres),
        "genres": configs,
    }


@router.post("/video/preview-theme", response_model=dict[str, Any])
@limiter.limit("30/minute")
def preview_genre_theme(
    request: Request,
    genre: str = Query(min_length=1, max_length=100),
) -> dict[str, Any]:
    """Show theme colors and visualizer type for a genre."""
    from ..services.genre_visualizer import get_genre_with_config
    
    try:
        config = get_genre_with_config(genre)
        return {
            "genre": config["genre"],
            "visualizer_type": config["visualizer_type"],
            "primary_color": config["colors"][0] if config["colors"] else "#FFFFFF",
            "secondary_colors": config["colors"][1:] if len(config["colors"]) > 1 else [],
            "lyrics_position": config["lyrics_position"],
            "lyrics_font_size": config["lyrics_font_size"],
            "background_color": config["background_color"],
            "tempo_sync": config["tempo_sync"],
        }
    except Exception as exc:
        raise ApiError(
            400,
            "INVALID_GENRE",
            f"Genre '{genre}' is not supported or could not be loaded."
        ) from exc


@router.post(
    "/songs/{song_id}/video-renders-themed",
    response_model=VideoRenderOut,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/hour")
def create_genre_themed_video_render(
    request: Request,
    song_id: str,
    asset_id: str = Query(min_length=1),
    genre: str | None = Query(default=None, max_length=100),
    lyrics: str | None = Query(default=None, max_length=30000),
    background: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> VideoRenderOut:
    """Generate genre-themed lyric video with always-visible lyrics.
    
    Auto-detects genre if not specified. Renders visualizer with synchronized lyrics
    that remain visible throughout the video based on genre-specific theming.
    """
    song = _get_song(db, song_id, owner_id)
    
    if not _latest_rights_declaration(db, owner_id, song_id):
        raise ApiError(
            403,
            "RIGHTS_DECLARATION_REQUIRED",
            "A current rights declaration is required to create promotional media.",
        )
    if not has_active_consent(db, owner_id, "audio_processing", song_id) or not has_active_consent(
        db,
        owner_id,
        "promotional_asset_generation",
        song_id,
    ):
        raise ApiError(403, "CONSENT_REQUIRED", "Audio-processing and promotional-media consent are required.")
    
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.song_id == song_id,
        MediaAsset.owner_id == owner_id,
        MediaAsset.asset_kind == "audio_original",
        MediaAsset.status == "ready",
    ).first()
    if asset is None or asset.duration_seconds is None:
        raise ApiError(409, "RESOURCE_NOT_READY", "A verified original audio asset is required.")
    
    if not renderer_capabilities().get("music_visualizer", False):
        raise ApiError(503, "VIDEO_RENDERER_UNAVAILABLE", "The local FFmpeg video renderer is unavailable.")
    
    # Import genre services
    from ..services.genre_visualizer import load_genre_theme, detect_genre_from_metadata
    from ..services.lyrics_renderer import format_lyrics_for_timing
    
    # Detect or use specified genre
    detected_genre = detect_genre_from_metadata(
        {},
        song_title=song.title,
        artist_name=song.artist_name,
        genre_preferences=song.genre_preferences or [],
    )
    
    if genre:
        final_genre = genre.lower().strip()
    else:
        final_genre = detected_genre
    
    try:
        theme = load_genre_theme(final_genre)
    except Exception as exc:
        logger.warning("genre_load_failed", extra={"genre": final_genre})
        theme = load_genre_theme("electronic")
    
    # Format lyrics if provided
    formatted_lyrics = []
    if lyrics and lyrics.strip():
        formatted_lyrics = format_lyrics_for_timing(lyrics.strip())
    
    operation = f"video-render-themed:create:{song_id}"
    request_hash = hashlib.sha256(
        json.dumps({
            "asset_id": asset_id,
            "genre": final_genre,
            "lyrics_hash": hashlib.sha256((lyrics or "").encode()).hexdigest(),
        }, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    
    prior = db.query(IdempotencyRecord).filter(
        IdempotencyRecord.owner_id == owner_id,
        IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == idempotency_key,
    ).first()
    if prior is not None:
        if prior.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used with a different request.")
        prior_render_id = prior.response_json.get("render_id")
        prior_render = db.query(VideoRender).filter(
            VideoRender.id == prior_render_id,
            VideoRender.owner_id == owner_id,
        ).first()
        if prior_render is None:
            raise ApiError(409, "JOB_STATE_INVALID", "The prior render request is no longer available.")
        return _video_render_response(prior_render)
    
    render_id = new_id()
    job = AnalysisJob(
        owner_id=owner_id,
        task_type="video_render_themed",
        subject_id=render_id,
    )
    db.add(job)
    db.flush()
    
    scene_plan = build_scene_plan(asset.duration_seconds, "music_visualizer")
    render = VideoRender(
        id=render_id,
        owner_id=owner_id,
        song_id=song.id,
        asset_id=asset.id,
        job_id=job.id,
        render_format="music_visualizer",
        status="queued",
        stage="queued",
        progress_percent=0,
        render_settings_json={
            "renderer": "local_ffmpeg_motion_graphics_genre_themed",
            "genre": final_genre,
            "resolution": "1280x720",
            "frame_rate": 30,
            "video_codec": "h264",
            "audio_codec": "aac",
            "uses_uploaded_artwork": False,
            "uses_ai_generated_footage": False,
            "lyrics_visible": len(formatted_lyrics) > 0,
            "visualizer_type": theme.visualizer_type,
        },
        scene_plan_json=scene_plan,
        provenance_json={
            "source_asset_id": asset.id,
            "source_sha256": asset.checksum_sha256,
            "visual_generation": f"genre-aware FFmpeg {theme.visualizer_type} with always-visible lyrics",
            "model": None,
            "artwork": "not used",
            "publishing": "not performed",
            "genre": final_genre,
        },
        output_metadata_json={
            "genre": final_genre,
            "lyrics_count": len(formatted_lyrics),
            "visualizer_type": theme.visualizer_type,
        },
    )
    db.add(render)
    db.add(
        IdempotencyRecord(
            owner_id=owner_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_json={"render_id": render.id},
        )
    )
    db.commit()
    db.refresh(render)
    
    # Store lyrics in temporary format for job runner
    # This will be passed to the rendering job
    background.add_task(
        run_v1_job,
        job.id,
        False,  # generate_ai_report
        False,  # allow_third_party_ai
    )
    
    logger.info("themed_video_render_created", extra={
        "render_id": render_id,
        "genre": final_genre,
        "song_id": song_id,
        "lyrics_count": len(formatted_lyrics),
    })
    
    return _video_render_response(render)


# ============================================================================
# MARKETING CAMPAIGN PLANNER ROUTES
# ============================================================================


def _campaign_response(campaign: MarketingCampaign, song: StudioSong) -> CampaignOut:
    """Convert MarketingCampaign model to response schema."""
    goals = []
    if campaign.goals:
        goals = campaign.goals.split(",") if isinstance(campaign.goals, str) else campaign.goals
    
    return CampaignOut(
        campaign_id=campaign.id,
        song_id=campaign.song_id,
        song_title=song.title,
        artist_name=song.artist_name,
        budget_usd=campaign.budget_usd,
        release_date=campaign.release_date,
        campaign_duration_days=campaign.campaign_duration_days,
        target_audience=campaign.target_audience,
        target_country=campaign.target_country,
        goals=goals,
        marketing_mix_preference=campaign.marketing_mix_preference or "combination",
        audience_size=campaign.artist_audience_size,
        song_quality_score=campaign.song_quality_score,
        budget_breakdown=campaign.budget_breakdown_json,
        campaign_plan=campaign.campaign_plan_json,
        captions_data=campaign.captions_json,
        posting_schedule=campaign.posting_schedule_json,
        ollama_model_used=campaign.ollama_model_used,
        ollama_response_tokens=campaign.ollama_response_tokens,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


@router.post(
    "/campaigns",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign(
    payload: CampaignCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
) -> CampaignOut:
    """Create a new marketing campaign for a song."""
    # Verify budget minimum
    if payload.budget_usd < 100.0:
        raise ApiError(
            400,
            "INVALID_BUDGET",
            f"Campaign budget must be at least $100 USD. Got ${payload.budget_usd}",
        )
    
    # Verify song ownership
    song = _get_song(db, payload.song_id, owner_id)
    
    # Get latest song analysis if available
    analysis = (
        db.query(SongAnalysis)
        .filter(
            SongAnalysis.song_id == payload.song_id,
            SongAnalysis.owner_id == owner_id,
            SongAnalysis.status == "succeeded",
        )
        .order_by(desc(SongAnalysis.created_at))
        .first()
    )
    
    # Check idempotency
    operation = f"campaign:create:{payload.song_id}"
    request_hash = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    
    prior = db.query(IdempotencyRecord).filter(
        IdempotencyRecord.owner_id == owner_id,
        IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == idempotency_key,
    ).first()
    
    if prior:
        if prior.request_hash != request_hash:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "This idempotency key was used with a different request.")
        # Return prior campaign if it exists
        prior_campaign = db.query(MarketingCampaign).filter(
            MarketingCampaign.id == prior.response_json.get("campaign_id")
        ).first()
        if prior_campaign:
            return _campaign_response(prior_campaign, song)
    
    # Calculate budget breakdown
    try:
        budget_breakdown = allocate_budget(payload.budget_usd, payload.goals)
    except ValueError as e:
        raise ApiError(400, "INVALID_BUDGET", str(e))
    
    # Create campaign record (initial state)
    goals_str = ",".join(payload.goals) if payload.goals else ""
    campaign = MarketingCampaign(
        id=new_id(),
        owner_id=owner_id,
        song_id=payload.song_id,
        budget_usd=payload.budget_usd,
        release_date=payload.release_date,
        campaign_duration_days=payload.campaign_duration_days,
        target_audience=payload.target_audience,
        target_country=payload.target_country or "US",
        goals=goals_str,
        marketing_mix_preference=payload.marketing_mix_preference,
        artist_audience_size=payload.audience_size,
        prefer_organic="organic" in payload.marketing_mix_preference.lower(),
        prefer_paid_ads="paid" in payload.marketing_mix_preference.lower(),
        prefer_influencer="influencer" in payload.marketing_mix_preference.lower(),
        budget_breakdown_json=budget_breakdown,
        song_quality_score=7,  # Default, will be updated
    )
    db.add(campaign)
    db.flush()
    
    # Store idempotency record
    db.add(
        IdempotencyRecord(
            owner_id=owner_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            response_json={"campaign_id": campaign.id},
        )
    )
    db.commit()
    
    # Generate campaign content in background
    background.add_task(
        _generate_campaign_content,
        campaign.id,
        payload.song_id,
        owner_id,
    )
    
    return _campaign_response(campaign, song)


def _generate_campaign_content(campaign_id: str, song_id: str, owner_id: str) -> None:
    """Background task to generate campaign content via Ollama."""
    from ..database import SessionLocal
    
    db = SessionLocal()
    try:
        campaign = db.query(MarketingCampaign).filter(
            MarketingCampaign.id == campaign_id,
            MarketingCampaign.owner_id == owner_id,
        ).first()
        
        if not campaign:
            logger.warning("campaign_generation_campaign_not_found", extra={"campaign_id": campaign_id})
            return
        
        song = db.query(StudioSong).filter(StudioSong.id == song_id).first()
        if not song:
            logger.warning("campaign_generation_song_not_found", extra={"song_id": song_id})
            return
        
        # Get song analysis if available
        analysis = (
            db.query(SongAnalysis)
            .filter(
                SongAnalysis.song_id == song_id,
                SongAnalysis.owner_id == owner_id,
                SongAnalysis.status == "succeeded",
            )
            .order_by(desc(SongAnalysis.created_at))
            .first()
        )
        
        intelligence_json = analysis.intelligence_json if analysis else None
        
        # Generate content sections
        ollama_available = check_ollama_available()
        
        # Song quality report
        quality_report = generate_song_quality_report(intelligence_json, song)
        campaign.song_quality_score = quality_report.get("score", 7)
        campaign.ollama_model_used = settings.ollama_model if ollama_available else "template"
        
        # Campaign plan
        campaign_plan = generate_campaign_plan(
            intelligence_json,
            song,
            campaign.budget_usd,
            campaign.goals.split(",") if campaign.goals else [],
            campaign.target_audience,
            campaign.release_date,
        )
        campaign.campaign_plan_json = campaign_plan
        
        # Captions and concepts
        captions = generate_captions_and_concepts(
            intelligence_json,
            song,
            campaign.budget_breakdown_json.get("allocations", []),
        )
        campaign.captions_json = captions
        
        # Posting schedule
        posting_schedule = generate_posting_schedule(
            campaign.campaign_duration_days,
            campaign.release_date,
        )
        campaign.posting_schedule_json = posting_schedule
        
        db.commit()
        logger.info("campaign_generation_completed", extra={"campaign_id": campaign_id})
    except Exception as e:
        logger.error("campaign_generation_failed", extra={"campaign_id": campaign_id, "error": str(e)})
    finally:
        db.close()


@router.get("/campaigns", response_model=CampaignListOut)
def list_campaigns(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> CampaignListOut:
    """List campaigns for the owner, newest first."""
    campaigns = (
        db.query(MarketingCampaign)
        .filter(MarketingCampaign.owner_id == owner_id)
        .order_by(desc(MarketingCampaign.created_at), desc(MarketingCampaign.id))
        .limit(limit)
        .offset(offset)
        .all()
    )
    
    total_count = db.query(MarketingCampaign).filter(
        MarketingCampaign.owner_id == owner_id
    ).count()
    
    items = []
    for campaign in campaigns:
        song = db.query(StudioSong).filter(StudioSong.id == campaign.song_id).first()
        if song:
            items.append(_campaign_response(campaign, song))
    
    return CampaignListOut(items=items, total_count=total_count)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> CampaignOut:
    """Fetch a single campaign by ID."""
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise ApiError(404, "CAMPAIGN_NOT_FOUND", "Campaign was not found.")
    
    song = db.query(StudioSong).filter(StudioSong.id == campaign.song_id).first()
    if not song:
        raise ApiError(500, "INTERNAL_ERROR", "Associated song not found.")
    
    return _campaign_response(campaign, song)


@router.get("/campaigns/{campaign_id}/report.pdf")
def get_campaign_pdf(
    campaign_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> StreamingResponse:
    """Download campaign report as PDF."""
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise ApiError(404, "CAMPAIGN_NOT_FOUND", "Campaign was not found.")
    
    song = db.query(StudioSong).filter(StudioSong.id == campaign.song_id).first()
    if not song:
        raise ApiError(500, "INTERNAL_ERROR", "Associated song not found.")
    
    # Get analysis if available
    analysis = (
        db.query(SongAnalysis)
        .filter(
            SongAnalysis.song_id == campaign.song_id,
            SongAnalysis.owner_id == owner_id,
            SongAnalysis.status == "succeeded",
        )
        .order_by(desc(SongAnalysis.created_at))
        .first()
    )
    
    intelligence_json = analysis.intelligence_json if analysis else None
    
    # Generate PDF
    try:
        pdf_bytes = generate_campaign_pdf(campaign, song, intelligence_json)
    except Exception as e:
        logger.error("pdf_generation_failed", extra={"campaign_id": campaign_id, "error": str(e)})
        raise ApiError(500, "PDF_GENERATION_FAILED", "Failed to generate PDF report.")
    
    # Return as streaming response
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"campaign-{campaign_id}.pdf\"",
        },
    )


@router.patch("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: str,
    payload: CampaignPatch,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> CampaignOut:
    """Update mutable fields of a campaign; optionally regenerate content."""
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise ApiError(404, "CAMPAIGN_NOT_FOUND", "Campaign was not found.")
    
    song = db.query(StudioSong).filter(StudioSong.id == campaign.song_id).first()
    if not song:
        raise ApiError(500, "INTERNAL_ERROR", "Associated song not found.")
    
    # Apply updates
    updates = payload.model_dump(exclude_unset=True, exclude={"regenerate"})
    
    if "budget_usd" in updates:
        new_budget = updates["budget_usd"]
        if new_budget < 100.0:
            raise ApiError(400, "INVALID_BUDGET", "Budget must be at least $100 USD.")
        campaign.budget_usd = new_budget
        # Recalculate budget breakdown
        campaign.budget_breakdown_json = allocate_budget(new_budget, campaign.goals.split(",") if campaign.goals else [])
    
    if "release_date" in updates:
        campaign.release_date = updates["release_date"]
    
    if "campaign_duration_days" in updates:
        campaign.campaign_duration_days = updates["campaign_duration_days"]
    
    if "target_audience" in updates:
        campaign.target_audience = updates["target_audience"]
    
    if "target_country" in updates:
        campaign.target_country = updates["target_country"]
    
    if "goals" in updates:
        campaign.goals = ",".join(updates["goals"]) if updates["goals"] else ""
    
    campaign.updated_at = _utcnow()
    db.commit()
    
    # Regenerate if requested
    if payload.regenerate:
        background.add_task(
            _generate_campaign_content,
            campaign.id,
            campaign.song_id,
            owner_id,
        )
    
    return _campaign_response(campaign, song)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    owner_id: str = Depends(current_owner),
) -> None:
    """Delete a campaign."""
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise ApiError(404, "CAMPAIGN_NOT_FOUND", "Campaign was not found.")
    
    db.delete(campaign)
    db.commit()

