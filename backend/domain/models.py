"""Persistence models for private assets, analysis jobs, intelligence, and reports."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudioSong(Base):
    __tablename__ = "v1_songs"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    artist_name = Column(String(255), nullable=True)
    language = Column(String(32), nullable=True)
    genre_preferences = Column(JSON, nullable=False, default=list)
    release_goal = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    assets = relationship("MediaAsset", back_populates="song", cascade="all, delete-orphan")
    analyses = relationship("SongAnalysis", back_populates="song", cascade="all, delete-orphan")
    campaigns = relationship("MarketingCampaign", back_populates="song", cascade="all, delete-orphan")


class ArtistWorkspaceProfile(Base):
    __tablename__ = "v1_artist_profiles"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_v1_artist_profile_owner"),)

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    display_name = Column(String(120), nullable=False)
    bio = Column(Text, nullable=True)
    primary_genre = Column(String(80), nullable=True)
    language = Column(String(32), nullable=True)
    territories = Column(JSON, nullable=False, default=list)
    goals = Column(JSON, nullable=False, default=list)
    brand_voice = Column(Text, nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class RightsDeclaration(Base):
    __tablename__ = "v1_rights_declarations"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    recording_rights_basis = Column(String(24), nullable=False)
    composition_rights_basis = Column(String(24), nullable=False)
    rights_confirmed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ConsentRecord(Base):
    __tablename__ = "v1_consent_records"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    consent_type = Column(String(48), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=True, index=True)
    granted = Column(Boolean, nullable=False)
    withdraws_consent_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class MediaAsset(Base):
    __tablename__ = "v1_media_assets"

    id = Column(String(36), primary_key=True, default=new_id)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(120), nullable=False, index=True)
    asset_kind = Column(String(40), nullable=False, default="audio_original")
    filename = Column(String(255), nullable=False)
    declared_content_type = Column(String(120), nullable=True)
    status = Column(String(24), nullable=False, default="pending_upload", index=True)
    storage_key = Column(String(80), nullable=False, unique=True)
    expected_size_bytes = Column(Integer, nullable=False)
    size_bytes = Column(Integer, nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    actual_content_type = Column(String(120), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: utcnow() + timedelta(minutes=15),
    )
    song = relationship("StudioSong", back_populates="assets")


class AnalysisJob(Base):
    __tablename__ = "v1_jobs"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    task_type = Column(String(40), nullable=False)
    subject_id = Column(String(36), nullable=True, index=True)
    status = Column(String(24), nullable=False, default="queued", index=True)
    stage = Column(String(48), nullable=False, default="queued")
    attempt = Column(Integer, nullable=False, default=1)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    analysis = relationship("SongAnalysis", back_populates="job", uselist=False)


class SongAnalysis(Base):
    __tablename__ = "v1_analyses"

    id = Column(String(36), primary_key=True, default=new_id)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("v1_media_assets.id"), nullable=False)
    owner_id = Column(String(120), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("v1_jobs.id"), nullable=False, unique=True)
    status = Column(String(24), nullable=False, default="queued", index=True)
    stage = Column(String(48), nullable=False, default="queued")
    progress_percent = Column(Integer, nullable=True)
    schema_version = Column(String(20), nullable=False, default="1.1")
    analysis_version = Column(String(40), nullable=False, default="standard_v1")
    intelligence_json = Column(JSON, nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    song = relationship("StudioSong", back_populates="analyses")
    asset = relationship("MediaAsset")
    job = relationship("AnalysisJob", back_populates="analysis")
    report = relationship("AnalysisReport", back_populates="analysis", uselist=False, cascade="all, delete-orphan")
    lyrics = relationship("SongAnalysisLyrics", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class SongAnalysisLyrics(Base):
    __tablename__ = "v1_analysis_lyrics"

    id = Column(String(36), primary_key=True, default=new_id)
    analysis_id = Column(
        String(36),
        ForeignKey("v1_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    analysis_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    analysis = relationship("SongAnalysis", back_populates="lyrics")


class AgentPipelineRun(Base):
    __tablename__ = "v1_agent_pipeline_runs"
    __table_args__ = (UniqueConstraint("analysis_id", name="uq_v1_agent_pipeline_analysis"),)

    id = Column(String(36), primary_key=True, default=new_id)
    analysis_id = Column(
        String(36),
        ForeignKey("v1_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id = Column(String(120), nullable=False, index=True)
    results_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    analysis = relationship("SongAnalysis")


class AnalysisReport(Base):
    __tablename__ = "v1_analysis_reports"

    id = Column(String(36), primary_key=True, default=new_id)
    analysis_id = Column(String(36), ForeignKey("v1_analyses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(160), nullable=True)
    prompt_version = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    analysis = relationship("SongAnalysis", back_populates="report")


class ReleasePlan(Base):
    __tablename__ = "v1_release_plans"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(String(36), ForeignKey("v1_analyses.id", ondelete="SET NULL"), nullable=True, index=True)
    release_date = Column(Date, nullable=True)
    goal = Column(Text, nullable=True)
    status = Column(String(24), nullable=False, default="draft", index=True)
    tasks_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    approved_at = Column(DateTime(timezone=True), nullable=True)


class VideoRender(Base):
    __tablename__ = "v1_video_renders"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("v1_media_assets.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("v1_jobs.id"), nullable=False, unique=True)
    render_format = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False, default="queued", index=True)
    stage = Column(String(48), nullable=False, default="queued")
    progress_percent = Column(Integer, nullable=False, default=0)
    error_code = Column(String(80), nullable=True)
    render_settings_json = Column(JSON, nullable=False)
    scene_plan_json = Column(JSON, nullable=False)
    provenance_json = Column(JSON, nullable=False)
    output_metadata_json = Column(JSON, nullable=True)
    output_checksum_sha256 = Column(String(64), nullable=True)
    output_size_bytes = Column(Integer, nullable=True)
    platform_urls = Column(JSON, nullable=True, default=dict)
    metadata_json = Column(JSON, nullable=True)
    publish_status = Column(String(24), nullable=False, default="none")
    publish_error = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PlatformConnection(Base):
    __tablename__ = "v1_platform_connections"
    __table_args__ = (UniqueConstraint("owner_id", "provider", name="uq_v1_platform_connection_owner_provider"),)

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    provider = Column(String(24), nullable=False)
    account_id = Column(String(255), nullable=True)
    account_name = Column(String(255), nullable=True)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    granted_scopes_json = Column(JSON, nullable=False, default=list)
    access_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(24), nullable=False, default="connected", index=True)
    connected_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)


class PlatformOAuthState(Base):
    __tablename__ = "v1_platform_oauth_states"

    state_hash = Column(String(64), primary_key=True)
    owner_id = Column(String(120), nullable=False, index=True)
    provider = Column(String(24), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "v1_idempotency_records"
    __table_args__ = (
        UniqueConstraint("owner_id", "operation", "key", name="uq_v1_idempotency_scope"),
    )

    id = Column(Integer, primary_key=True)
    owner_id = Column(String(120), nullable=False)
    operation = Column(String(120), nullable=False)
    key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


Index("ix_v1_analysis_song_created", SongAnalysis.song_id, SongAnalysis.created_at)


class MarketingCampaign(Base):
    __tablename__ = "v1_marketing_campaigns"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(120), nullable=False, index=True)
    song_id = Column(String(36), ForeignKey("v1_songs.id", ondelete="CASCADE"), nullable=False, index=True)
    budget_usd = Column(Float, nullable=False)
    release_date = Column(Date, nullable=True)
    campaign_duration_days = Column(Integer, nullable=False, default=28)
    target_audience = Column(String(255), nullable=True)
    target_country = Column(String(80), nullable=True)
    goals = Column(String(255), nullable=True)
    marketing_mix_preference = Column(String(100), nullable=True)
    artist_audience_size = Column(Integer, nullable=True)
    prefer_organic = Column(Boolean, nullable=False, default=False)
    prefer_paid_ads = Column(Boolean, nullable=False, default=False)
    prefer_influencer = Column(Boolean, nullable=False, default=False)
    campaign_plan_json = Column(JSON, nullable=True)
    budget_breakdown_json = Column(JSON, nullable=False, default=dict)
    captions_json = Column(JSON, nullable=False, default=dict)
    posting_schedule_json = Column(JSON, nullable=False, default=dict)
    song_quality_score = Column(Integer, nullable=False, default=5)
    reach_projection = Column(Integer, nullable=False, default=0)
    ollama_model_used = Column(String(100), nullable=True)
    ollama_response_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    song = relationship("StudioSong", back_populates="campaigns")

