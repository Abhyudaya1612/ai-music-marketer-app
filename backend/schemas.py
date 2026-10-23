"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SongCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    artist: str = Field(..., min_length=1, max_length=255)
    genre: str = ""
    lyrics: str = ""
    # optional pre-measured audio features
    bpm: Optional[float] = None
    musical_key: Optional[str] = Field(None, max_length=10)
    energy: Optional[float] = Field(None, ge=0.0, le=1.0)
    valence: Optional[float] = Field(None, ge=0.0, le=1.0)


class SongOut(BaseModel):
    id: int
    title: str
    artist: str
    genre: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ---------- nested detail payloads ----------
class IntelligenceOut(BaseModel):
    bpm: float
    musical_key: str
    energy: float
    valence: float
    mood: str
    structure: list[str]
    hooks: list[str]
    lyrical_themes: list[str]
    production_notes: list[str]
    a_r_insights: list[str]
    model_config = {"from_attributes": True}


class SegmentOut(BaseModel):
    name: str
    description: str
    age_range: str
    interests: list[str]
    platform_affinity: dict
    match_score: float
    is_primary: bool
    rank: int
    model_config = {"from_attributes": True}


class ContentPieceOut(BaseModel):
    format: str
    hook: str
    concept: str
    caption: str
    cta: str
    sound_strategy: str
    sort_index: int
    model_config = {"from_attributes": True}


class StrategyOut(BaseModel):
    release_type: str
    timeline_weeks: int
    phases: dict
    platform_priority: list[str]
    budget_allocation: dict
    pitch_targets: list[str]
    key_message: str
    model_config = {"from_attributes": True}


class MetricsOut(BaseModel):
    streams: int
    saves: int
    playlist_adds: int
    social_views: int
    engagement_rate: float
    follower_delta: int
    score: float
    model_config = {"from_attributes": True}


class OptimizationOut(BaseModel):
    what_worked: list[str]
    what_underperformed: list[str]
    recommendations: list[str]
    lessons_learned: list[str]
    model_config = {"from_attributes": True}


class FinalOut(BaseModel):
    orchestrator_summary: str
    top_priority_actions: list[str]
    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: int
    status: str
    error: Optional[str]
    logs: list[str]
    started_at: datetime
    finished_at: Optional[datetime]
    intelligence: Optional[IntelligenceOut] = None
    segments: list[SegmentOut] = []
    content_pieces: list[ContentPieceOut] = []
    strategy: Optional[StrategyOut] = None
    metrics: Optional[MetricsOut] = None
    optimization: Optional[OptimizationOut] = None
    final_strategy: Optional[FinalOut] = None
    model_config = {"from_attributes": True}


class SongDetailOut(SongOut):
    lyrics: str
    runs: list[RunOut] = []


class CampaignTaskOut(BaseModel):
    id: int
    name: str
    channel: str
    owner: str
    priority: str
    due_in_days: int
    status: str
    description: str
    model_config = {"from_attributes": True}


class CampaignPlanOut(BaseModel):
    id: int
    name: str
    objective: str
    status: str
    release_date: datetime
    budget_total: float
    channels: list[str]
    notes: str
    tasks: list[CampaignTaskOut] = []
    model_config = {"from_attributes": True}


class ArtistProfileOut(BaseModel):
    id: int
    name: str
    brand_voice: str
    target_audience: str
    goals: list[str]
    markets: list[str]
    model_config = {"from_attributes": True}


class ReleaseCalendarEntryOut(BaseModel):
    id: int
    title: str
    entry_type: str
    channel: str
    scheduled_for: datetime
    status: str
    notes: str
    model_config = {"from_attributes": True}


class CampaignTaskCreate(BaseModel):
    name: str
    channel: str = ""
    owner: str = "artist team"
    priority: str = "medium"
    due_in_days: int = 0
    status: str = "scheduled"
    description: str = ""


class CampaignPlanCreate(BaseModel):
    song_id: int
    name: str
    objective: str = "Grow streams and engagement"
    status: str = "planned"
    release_date: Optional[datetime] = None
    budget_total: float = 0.0
    channels: list[str] = Field(default_factory=lambda: ["TikTok", "Instagram", "Spotify"])
    notes: str = ""
    tasks: list[CampaignTaskCreate] = Field(default_factory=list)


class ArtistProfileCreate(BaseModel):
    name: str = "Artist"
    brand_voice: str = ""
    target_audience: str = ""
    goals: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)


class ReleaseCalendarEntryCreate(BaseModel):
    song_id: Optional[int] = None
    campaign_id: Optional[int] = None
    title: str
    entry_type: str = "campaign"
    channel: str = ""
    scheduled_for: Optional[datetime] = None
    status: str = "planned"
    notes: str = ""


class SongDetailOutWithCampaigns(SongDetailOut):
    campaigns: list[CampaignPlanOut] = Field(default_factory=list)
    release_calendar: list[ReleaseCalendarEntryOut] = Field(default_factory=list)


class StatsOut(BaseModel):
    total_songs: int
    analyzed_songs: int
    total_streams: int
    total_social_views: int
    total_new_followers: int
    avg_score: float
    top_platform: Optional[str] = None
    active_campaigns: int = 0
    avg_release_window_days: float = 0.0
    artist_goals: list[str] = Field(default_factory=list)
