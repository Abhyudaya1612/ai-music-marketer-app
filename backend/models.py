"""SQLAlchemy models — one normalized table per agent output.

    Song 1──* Run 1──1 SongIntelligence
                  1──* AudienceSegment
                  1──* ContentPiece
                  1──1 MarketingStrategy
                  1──1 PerformanceMetrics
                  1──1 OptimizationReport
                  1──1 FinalStrategy
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import (Column, Integer, String, Text, Float, DateTime,
                        ForeignKey, JSON, Boolean)
from sqlalchemy.orm import relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Song(Base):
    __tablename__ = "songs"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=False)
    genre = Column(String(120), default="")
    lyrics = Column(Text, default="")
    # optional pre-measured audio features (from Essentia/Librosa in prod)
    bpm = Column(Float, nullable=True)
    musical_key = Column(String(10), nullable=True)
    energy = Column(Float, nullable=True)
    valence = Column(Float, nullable=True)
    status = Column(String(20), default="pending")  # pending|analyzing|complete|failed
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    runs = relationship("Run", back_populates="song", cascade="all, delete-orphan",
                        order_by="Run.id.desc()")
    campaigns = relationship("CampaignPlan", back_populates="song",
                            cascade="all, delete-orphan")
    release_calendar = relationship("ReleaseCalendarEntry", back_populates="song",
                                   cascade="all, delete-orphan")


class CampaignPlan(Base):
    __tablename__ = "campaign_plans"
    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    objective = Column(String(255), default="")
    status = Column(String(30), default="planned")
    release_date = Column(DateTime(timezone=True), default=utcnow)
    budget_total = Column(Float, default=0.0)
    channels = Column(JSON, default=list)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    song = relationship("Song", back_populates="campaigns")
    tasks = relationship("CampaignTask", back_populates="campaign",
                        cascade="all, delete-orphan")
    release_calendar = relationship("ReleaseCalendarEntry", back_populates="campaign",
                                   cascade="all, delete-orphan")


class CampaignTask(Base):
    __tablename__ = "campaign_tasks"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaign_plans.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    channel = Column(String(120), default="")
    owner = Column(String(120), default="artist team")
    priority = Column(String(20), default="medium")
    due_in_days = Column(Integer, default=0)
    status = Column(String(20), default="scheduled")
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    campaign = relationship("CampaignPlan", back_populates="tasks")


class ArtistProfile(Base):
    __tablename__ = "artist_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), default="Artist")
    brand_voice = Column(String(255), default="")
    target_audience = Column(String(255), default="")
    goals = Column(JSON, default=list)
    markets = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class ReleaseCalendarEntry(Base):
    __tablename__ = "release_calendar_entries"
    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaign_plans.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    entry_type = Column(String(60), default="campaign")
    channel = Column(String(120), default="")
    scheduled_for = Column(DateTime(timezone=True), default=utcnow)
    status = Column(String(20), default="planned")
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    song = relationship("Song", back_populates="release_calendar")
    campaign = relationship("CampaignPlan", back_populates="release_calendar")


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="running")   # running|finished|failed
    error = Column(Text, nullable=True)
    logs = Column(JSON, default=list)                # agent audit trail
    started_at = Column(DateTime(timezone=True), default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    song = relationship("Song", back_populates="runs")
    intelligence = relationship("SongIntelligenceRow", back_populates="run",
                                uselist=False, cascade="all, delete-orphan")
    segments = relationship("AudienceSegmentRow", back_populates="run",
                            cascade="all, delete-orphan")
    content_pieces = relationship("ContentPieceRow", back_populates="run",
                                  cascade="all, delete-orphan")
    strategy = relationship("MarketingStrategyRow", back_populates="run",
                            uselist=False, cascade="all, delete-orphan")
    metrics = relationship("PerformanceMetricsRow", back_populates="run",
                           uselist=False, cascade="all, delete-orphan")
    optimization = relationship("OptimizationReportRow", back_populates="run",
                                uselist=False, cascade="all, delete-orphan")
    final_strategy = relationship("FinalStrategyRow", back_populates="run",
                                  uselist=False, cascade="all, delete-orphan")


class SongIntelligenceRow(Base):
    __tablename__ = "song_intelligence"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    bpm = Column(Float)
    musical_key = Column(String(10))
    energy = Column(Float)
    valence = Column(Float)
    mood = Column(String(255))
    structure = Column(JSON, default=list)
    hooks = Column(JSON, default=list)
    lyrical_themes = Column(JSON, default=list)
    production_notes = Column(JSON, default=list)
    a_r_insights = Column(JSON, default=list)
    run = relationship("Run", back_populates="intelligence")


class AudienceSegmentRow(Base):
    __tablename__ = "audience_segments"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"))
    name = Column(String(255))
    description = Column(Text)
    age_range = Column(String(20))
    interests = Column(JSON, default=list)
    platform_affinity = Column(JSON, default=dict)
    match_score = Column(Float)
    is_primary = Column(Boolean, default=False)
    rank = Column(Integer)
    run = relationship("Run", back_populates="segments")


class ContentPieceRow(Base):
    __tablename__ = "content_pieces"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"))
    format = Column(String(120))
    hook = Column(Text)
    concept = Column(Text)
    caption = Column(Text)
    cta = Column(Text)
    sound_strategy = Column(Text)
    sort_index = Column(Integer)
    run = relationship("Run", back_populates="content_pieces")


class MarketingStrategyRow(Base):
    __tablename__ = "marketing_strategies"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    release_type = Column(String(50))
    timeline_weeks = Column(Integer)
    phases = Column(JSON, default=dict)
    platform_priority = Column(JSON, default=list)
    budget_allocation = Column(JSON, default=dict)
    pitch_targets = Column(JSON, default=list)
    key_message = Column(Text)
    run = relationship("Run", back_populates="strategy")


class PerformanceMetricsRow(Base):
    __tablename__ = "performance_metrics"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    streams = Column(Integer)
    saves = Column(Integer)
    playlist_adds = Column(Integer)
    social_views = Column(Integer)
    engagement_rate = Column(Float)
    follower_delta = Column(Integer)
    score = Column(Float)
    run = relationship("Run", back_populates="metrics")


class OptimizationReportRow(Base):
    __tablename__ = "optimization_reports"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    what_worked = Column(JSON, default=list)
    what_underperformed = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    lessons_learned = Column(JSON, default=list)
    run = relationship("Run", back_populates="optimization")


class FinalStrategyRow(Base):
    __tablename__ = "final_strategies"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), unique=True)
    orchestrator_summary = Column(Text)
    top_priority_actions = Column(JSON, default=list)
    run = relationship("Run", back_populates="final_strategy")
