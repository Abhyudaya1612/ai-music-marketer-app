"""Structured data contracts exchanged between agents.

Every agent consumes and produces typed structures — agents never
exchange free-form text, only structured intelligence. This is what
makes the multi-agent coordination explicit and auditable.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------- Input ----------
@dataclass
class SongInput:
    title: str
    artist: str
    genre: str
    lyrics: str = ""
    audio_path: Optional[str] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    energy: Optional[float] = None          # 0.0 - 1.0
    valence: Optional[float] = None         # 0.0 - 1.0


# ---------- Music Analysis Agent ----------
@dataclass
class SongIntelligence:
    bpm: float
    musical_key: str
    energy: float
    valence: float
    mood: str
    structure: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    lyrical_themes: list[str] = field(default_factory=list)
    production_notes: list[str] = field(default_factory=list)
    a_r_insights: list[str] = field(default_factory=list)


# ---------- Audience Intelligence Agent ----------
@dataclass
class AudienceSegment:
    name: str
    description: str
    age_range: str
    interests: list[str]
    platform_affinity: dict
    match_score: float


@dataclass
class AudienceInsight:
    segments: list[AudienceSegment]
    primary_segment: str
    summary: str


# ---------- Content Strategy Agent ----------
@dataclass
class ContentPiece:
    format: str
    hook: str
    concept: str
    caption: str
    cta: str
    sound_strategy: str


@dataclass
class ContentPlan:
    pieces: list[ContentPiece]
    posting_cadence: str
    overarching_angle: str


# ---------- Marketing Strategy Agent ----------
@dataclass
class MarketingStrategy:
    release_type: str
    timeline_weeks: int
    phases: dict
    platform_priority: list[str]
    budget_allocation: dict
    pitch_targets: list[str]
    key_message: str


# ---------- Analytics & Optimization Agent ----------
@dataclass
class PerformanceMetrics:
    streams: int
    saves: int
    playlist_adds: int
    social_views: int
    engagement_rate: float
    follower_delta: int
    score: float


@dataclass
class OptimizationReport:
    metrics: PerformanceMetrics
    what_worked: list[str]
    what_underperformed: list[str]
    recommendations: list[str]
    lessons_learned: list[str]


# ---------- Orchestrator final output ----------
@dataclass
class FinalStrategy:
    orchestrator_summary: str
    top_priority_actions: list[str]


def to_dict(obj):
    return asdict(obj)
