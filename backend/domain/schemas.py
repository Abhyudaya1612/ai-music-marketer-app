"""Versioned request and response contracts for the first product slice."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SongCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    artist_name: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=32)
    genre_preferences: list[str] = Field(default_factory=list, max_length=20)
    release_goal: str | None = Field(default=None, max_length=2000)


class SongPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    artist_name: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=32)
    genre_preferences: list[str] | None = Field(default=None, max_length=20)
    release_goal: str | None = Field(default=None, max_length=2000)


class SongOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    song_id: str
    title: str
    artist_name: str | None
    language: str | None
    genre_preferences: list[str]
    release_goal: str | None
    created_at: datetime
    updated_at: datetime


class ArtistProfileUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    primary_genre: str | None = Field(default=None, max_length=80)
    language: str | None = Field(default=None, max_length=32)
    territories: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(
        default_factory=list,
        max_length=20,
    )
    goals: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(
        default_factory=list,
        max_length=20,
    )
    brand_voice: str | None = Field(default=None, max_length=1000)


class ArtistProfileOut(ArtistProfileUpsert):
    profile_id: str
    onboarding_completed_at: datetime
    updated_at: datetime


class SongListOut(BaseModel):
    items: list[SongOut]
    next_cursor: str | None = None
    total_count: int


ConsentType = Literal[
    "audio_processing",
    "third_party_ai",
    "derived_analysis_storage",
    "promotional_asset_generation",
    "publishing_scheduling",
    "platform_account_connection",
    "aggregate_analytics",
    "proprietary_model_training",
]


class ConsentCreate(BaseModel):
    consent_type: ConsentType
    song_id: str | None = None


class ConsentOut(BaseModel):
    consent_id: str
    consent_type: ConsentType
    song_id: str | None
    granted: bool
    withdraws_consent_id: str | None
    created_at: datetime


class ConsentListOut(BaseModel):
    items: list[ConsentOut]


class ConsentWithdrawalOut(ConsentOut):
    pass


class RightsDeclarationCreate(BaseModel):
    song_id: str
    recording_rights_basis: Literal["owned", "licensed", "authorized"]
    composition_rights_basis: Literal["owned", "licensed", "authorized"]
    rights_confirmed: Literal[True]


class RightsDeclarationOut(BaseModel):
    declaration_id: str
    song_id: str
    recording_rights_basis: Literal["owned", "licensed", "authorized"]
    composition_rights_basis: Literal["owned", "licensed", "authorized"]
    rights_confirmed: bool
    created_at: datetime


class RightsDeclarationListOut(BaseModel):
    items: list[RightsDeclarationOut]


class UploadIntentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    declared_content_type: str | None = Field(default=None, max_length=120)
    size_bytes: int = Field(gt=0)
    asset_kind: Literal["audio_original"] = "audio_original"


class UploadIntentResponse(BaseModel):
    asset_id: str
    upload_method: Literal["PUT"]
    upload_url: str
    required_headers: dict[str, str]
    expires_at: datetime


class AssetCompleteRequest(BaseModel):
    asset_id: str


class AssetOut(BaseModel):
    asset_id: str
    asset_kind: str
    status: str
    size_bytes: int | None
    checksum_sha256: str | None
    created_at: datetime


class AssetListOut(BaseModel):
    items: list[AssetOut]
    next_cursor: str | None = None


class AssetCompleteResponse(BaseModel):
    asset_id: str
    status: str
    job_id: str
    status_url: str


class AnalysisRequest(BaseModel):
    asset_id: str
    lyrics_asset_id: str | None = None
    lyrics: str | None = Field(default=None, max_length=30000)
    analysis_profile: Literal["standard_v1"] = "standard_v1"
    include_pretrained_predictions: bool = False
    generate_ai_report: bool = True
    allow_third_party_ai: bool = False


class AnalysisAccepted(BaseModel):
    analysis_id: str
    job_id: str
    status: str
    status_url: str
    requested_at: datetime


class SafeError(BaseModel):
    code: str
    message: str


class AnalysisStatusOut(BaseModel):
    analysis_id: str
    song_id: str
    status: str
    stage: str
    progress_percent: int | None
    created_at: datetime
    updated_at: datetime
    error: SafeError | None


class JobOut(BaseModel):
    job_id: str
    task_type: str
    status: str
    stage: str
    attempt: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: SafeError | None


class FeatureValue(BaseModel):
    value: float | int | str | dict[str, Any] | None
    status: Literal["measured", "derived", "estimated", "predicted", "unavailable"]
    unit: str | None = None
    source: str
    source_version: str | None = None
    limitations: list[str] = Field(default_factory=list)


class SongIntelligenceIn(BaseModel):
    """Validated schema for extracted song intelligence (audio features and analysis)."""
    audio_features: dict[str, FeatureValue]
    sections: list[dict[str, Any]] = Field(default_factory=list)
    hook_candidates: list[HookCandidate] = Field(default_factory=list)
    lyrics_analysis: dict[str, Any]
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)


class HookCandidate(BaseModel):
    start_seconds: float | None = None
    end_seconds: float | None = None
    kind: Literal["lyrical", "melodic", "rhythmic", "instrumental", "unknown"]
    text: str | None = None
    evidence: str


class SongIntelligenceOut(BaseModel):
    analysis_id: str
    song_id: str
    schema_version: str
    analysis_version: str
    created_at: datetime
    audio_features: dict[str, FeatureValue]
    sections: list[dict[str, Any]]
    hook_candidates: list[HookCandidate]
    lyrics_analysis: dict[str, Any]
    predictions: list[dict[str, Any]]
    limitations: list[str]
    provenance: list[dict[str, Any]]


class AgentPipelineOut(BaseModel):
    analysis_id: str
    song_id: str
    generated_at: datetime
    results: dict[str, Any]
    limitations: list[str]


class AudienceEvidence(BaseModel):
    source: str
    observation: str
    status: Literal["artist_provided", "keyword_derived", "measured", "estimated"]


class AudienceHypothesis(BaseModel):
    statement: str
    evidence: list[AudienceEvidence]
    artist_context: list[str]
    uncertainty: str
    validation_experiment: str


class AudienceHypothesesOut(BaseModel):
    analysis_id: str
    hypotheses: list[AudienceHypothesis]
    limitations: list[str]


class ReleasePlanCreate(BaseModel):
    song_id: str
    analysis_id: str | None = None
    release_date: date | None = None
    goal: str | None = Field(default=None, max_length=2000)


class ReleasePlanPatch(BaseModel):
    release_date: date | None = None
    goal: str | None = Field(default=None, max_length=2000)


class ReleasePlanTaskOut(BaseModel):
    task_id: str
    stage: Literal["pre_release", "release_day", "post_release"]
    title: str
    action: str
    day_offset: int
    planned_date: date | None
    depends_on: list[str]


class ReleasePlanOut(BaseModel):
    plan_id: str
    song_id: str
    analysis_id: str | None
    release_date: date | None
    goal: str | None
    status: Literal["draft", "approved"]
    tasks: list[ReleasePlanTaskOut]
    limitations: list[str]
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None


class ReleasePlanListOut(BaseModel):
    items: list[ReleasePlanOut]


class VideoRenderRequest(BaseModel):
    asset_id: str
    render_format: Literal["music_visualizer", "full_music_video"]


class VideoSceneOut(BaseModel):
    name: Literal["opening_title", "audio_reactive", "closing_card"]
    start_seconds: float
    end_seconds: float
    transition: Literal["fade", "cut"]


class VideoRenderOut(BaseModel):
    render_id: str
    song_id: str
    asset_id: str
    job_id: str
    render_format: Literal["music_visualizer", "full_music_video"]
    status: Literal["queued", "running", "succeeded", "failed"]
    stage: str
    progress_percent: int
    error: SafeError | None
    scene_plan: list[VideoSceneOut]
    provenance: dict[str, Any]
    output_metadata: dict[str, Any] | None
    output_size_bytes: int | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    status_url: str
    download_url: str | None


class VideoRenderListOut(BaseModel):
    items: list[VideoRenderOut]


PlatformProvider = Literal["youtube", "instagram", "facebook"]


class PlatformConnectionOut(BaseModel):
    provider: PlatformProvider
    configured: bool
    status: Literal["not_configured", "not_connected", "connected", "expired"]
    connected: bool
    account_id: str | None
    account_name: str | None
    granted_scopes: list[str]
    connected_at: datetime | None
    expires_at: datetime | None


class PlatformConnectionListOut(BaseModel):
    items: list[PlatformConnectionOut]


class OAuthStartOut(BaseModel):
    authorization_url: str
    expires_at: datetime


class EvidenceClaim(BaseModel):
    claim: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list)
    kind: Literal["observed", "measured", "predicted", "interpretation", "recommendation"]


class ARReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    strengths: list[EvidenceClaim] = Field(default_factory=list)
    improvement_opportunities: list[EvidenceClaim] = Field(default_factory=list)
    hook_candidates: list[EvidenceClaim] = Field(default_factory=list)
    recommendations: list[EvidenceClaim] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = "Decision support only; this report does not guarantee commercial success."


class ARReportOut(ARReportPayload):
    report_id: str
    analysis_id: str
    schema_version: str
    provider: str
    model: str | None
    prompt_version: str
    created_at: datetime


class ErrorDetails(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    error: ErrorDetails


class MetadataGenerationRequest(BaseModel):
    song_title: str = Field(min_length=1, max_length=255)
    artist_name: str = Field(min_length=1, max_length=255)
    duration_seconds: int = Field(gt=0)
    features: dict[str, Any] = Field(default_factory=dict)
    mood: str | None = Field(default=None, max_length=100)


class MetadataGenerationResponse(BaseModel):
    youtube_title: str = Field(max_length=100)
    youtube_description: str = Field(max_length=5000)
    youtube_tags: list[Annotated[str, Field(max_length=500)]]


class YouTubePublishRequest(BaseModel):
    render_id: str
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    tags: list[Annotated[str, Field(max_length=500)]] = Field(default_factory=list)
    is_public: bool = False


class YouTubePublishResponse(BaseModel):
    video_id: str
    url: str
    platform: Literal["youtube"] = "youtube"
    published_at: datetime


class GenreThemeConfig(BaseModel):
    """Genre-specific visualizer and lyrics styling configuration."""
    genre: str
    visualizer_type: Literal["waveform", "spectrum"]
    colors: list[str]
    lyrics_position: Literal["top", "bottom", "center", "flowing"]
    lyrics_font_family: str
    lyrics_font_size: int = Field(ge=24, le=96)
    tempo_sync: bool
    background_color: str


class LyricsRenderConfig(BaseModel):
    """Configuration for rendering lyrics on video."""
    lyrics: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {text, start_ms, end_ms} timing objects"
    )
    always_visible: bool = True
    position: Literal["top", "bottom", "center", "flowing"]
    font_size: int = Field(default=36, ge=24, le=96)
    color: str = Field(default="FFFFFF")
    background_color: str = Field(default="000000")


class GenreThemePreview(BaseModel):
    """Preview of genre theme for UI display."""
    genre: str
    visualizer_type: str
    primary_color: str
    secondary_colors: list[str]
    lyrics_position: str
    lyrics_font_size: int
    background_color: str


class VideoGenreTunedRenderRequest(BaseModel):
    """Request to render genre-themed lyric video."""
    asset_id: str
    genre: str | None = None
    lyrics: str | None = Field(default=None, max_length=30000)
    lyrics_format: Literal["plain", "srt", "lrc"] = "plain"
    render_format: Literal["music_visualizer", "full_music_video"] = "music_visualizer"


class VideoGenreTunedRenderOut(VideoRenderOut):
    """Extended render output with genre and lyrics metadata."""
    genre: str | None = None
    lyrics_visible: bool = True


# Campaign Planner Schemas

class CampaignCreate(BaseModel):
    song_id: str
    budget_usd: float = Field(gt=0)
    release_date: date | None = None
    campaign_duration_days: int = Field(default=28, ge=7, le=90)
    target_audience: str | None = Field(default=None, max_length=255)
    target_country: str | None = Field(default="US", max_length=80)
    preferred_platforms: list[str] = Field(default_factory=lambda: ["Instagram", "TikTok", "YouTube", "Spotify"], max_length=10)
    audience_size: int | None = Field(default=None, ge=0)
    goals: list[str] = Field(default_factory=list, max_length=20)
    marketing_mix_preference: str = Field(default="combination", max_length=100)


class CampaignPatch(BaseModel):
    budget_usd: float | None = Field(default=None, gt=0)
    release_date: date | None = None
    campaign_duration_days: int | None = Field(default=None, ge=7, le=90)
    target_audience: str | None = Field(default=None, max_length=255)
    target_country: str | None = Field(default=None, max_length=80)
    goals: list[str] | None = Field(default=None, max_length=20)
    regenerate: bool = False


class BudgetAllocationItem(BaseModel):
    channel: str
    amount: float
    percentage: float
    objective: str
    expected_deliverables: str
    priority: str


class BudgetBreakdownOut(BaseModel):
    tier: str
    total_budget: float
    allocations: list[BudgetAllocationItem]
    zero_budget_organic_strategy: list[dict[str, str]]


class PostingScheduleItem(BaseModel):
    date: str
    day: str
    posting_time: str
    platform: str
    content_type: str
    caption_idea: str
    call_to_action: str
    required_assets: list[str]
    paid_promotion_status: str
    paid_budget: float
    phase: str


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: str
    song_id: str
    song_title: str
    artist_name: str | None
    budget_usd: float
    release_date: date | None
    campaign_duration_days: int
    target_audience: str | None
    target_country: str | None
    goals: list[str]
    marketing_mix_preference: str
    audience_size: int | None
    song_quality_score: int
    budget_breakdown: dict[str, Any] | None
    campaign_plan: dict[str, Any] | None
    captions_data: dict[str, Any] | None
    posting_schedule: list[PostingScheduleItem] | None
    ollama_model_used: str | None
    ollama_response_tokens: int
    created_at: datetime
    updated_at: datetime


class CampaignListOut(BaseModel):
    items: list[CampaignOut]
    total_count: int


class MarketingCampaignCreate(BaseModel):
    song_id: str
    budget_usd: float = Field(ge=100)
    release_date: date | None = None
    campaign_duration_days: int = Field(default=28, ge=7, le=90)
    target_audience: str | None = Field(default=None, max_length=255)
    target_country: str | None = Field(default=None, max_length=80)
    goals: str | None = Field(default=None, max_length=255)
    artist_audience_size: int | None = Field(default=None, ge=0)
    prefer_organic: bool = False
    prefer_paid_ads: bool = False
    prefer_influencer: bool = False


class BudgetAllocationItem(BaseModel):
    platform: str
    amount_usd: float
    percentage: float
    objective: str
    deliverables: str
    priority: str


class MarketingCampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: str
    song_id: str
    budget_usd: float
    release_date: date | None
    campaign_duration_days: int
    target_audience: str | None
    target_country: str | None
    goals: str | None
    artist_audience_size: int | None
    marketing_mix_preference: str | None
    song_quality_score: int
    reach_projection: int
    budget_breakdown: list[BudgetAllocationItem]
    captions: dict[str, Any]
    posting_schedule: list[dict[str, Any]]
    campaign_plan: dict[str, Any] | None
    ollama_model_used: str | None
    created_at: datetime
    updated_at: datetime


class MarketingCampaignListOut(BaseModel):
    items: list[MarketingCampaignOut]
    next_cursor: str | None = None
    total_count: int
