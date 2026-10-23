export type Song = {
  song_id: string;
  title: string;
  artist_name: string | null;
  language: string | null;
  genre_preferences: string[];
  release_goal: string | null;
  created_at: string;
  updated_at: string;
};

export type ArtistProfile = {
  profile_id: string;
  display_name: string;
  bio: string | null;
  primary_genre: string | null;
  language: string | null;
  territories: string[];
  goals: string[];
  brand_voice: string | null;
  onboarding_completed_at: string;
  updated_at: string;
};

export type ArtistProfilePayload = Omit<
  ArtistProfile,
  "profile_id" | "onboarding_completed_at" | "updated_at"
>;

export type SongList = {
  items: Song[];
  next_cursor: string | null;
  total_count: number;
};

export type ConsentType =
  | "audio_processing"
  | "third_party_ai"
  | "derived_analysis_storage"
  | "promotional_asset_generation"
  | "publishing_scheduling"
  | "platform_account_connection"
  | "aggregate_analytics"
  | "proprietary_model_training";

export type ConsentRecord = {
  consent_id: string;
  consent_type: ConsentType;
  song_id: string | null;
  granted: boolean;
  withdraws_consent_id: string | null;
  created_at: string;
};

export type ConsentList = {
  items: ConsentRecord[];
};

export type PlatformProvider = "youtube" | "instagram" | "facebook";

export type PlatformConnection = {
  provider: PlatformProvider;
  configured: boolean;
  status: "not_configured" | "not_connected" | "connected" | "expired";
  connected: boolean;
  account_id: string | null;
  account_name: string | null;
  granted_scopes: string[];
  connected_at: string | null;
  expires_at: string | null;
};

export type PlatformConnectionList = { items: PlatformConnection[] };

export type OAuthStart = {
  authorization_url: string;
  expires_at: string;
};

export type Job = {
  job_id: string;
  task_type: string;
  status: string;
  stage: string;
  attempt: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: { code: string; message: string } | null;
};

export type FeatureValue = {
  value: number | string | Record<string, unknown> | null;
  status: "measured" | "derived" | "estimated" | "predicted" | "unavailable";
  unit: string | null;
  source: string;
  source_version: string | null;
  limitations: string[];
};

export type Intelligence = {
  analysis_id: string;
  song_id: string;
  schema_version: string;
  analysis_version: string;
  created_at: string;
  audio_features: Record<string, FeatureValue>;
  sections: Array<{
    label: string;
    start_seconds: number;
    end_seconds: number;
    evidence: string;
  }>;
  hook_candidates: Array<{
    start_seconds: number | null;
    end_seconds: number | null;
    kind: "lyrical" | "melodic" | "rhythmic" | "instrumental" | "unknown";
    text: string | null;
    evidence: string;
  }>;
  lyrics_analysis: {
    available: boolean;
    status: string;
    themes: string[];
    candidate_lines: Array<{ text: string; evidence: string; occurrences: number }>;
    reason?: string;
  };
  predictions: Array<Record<string, unknown>>;
  limitations: string[];
  provenance: Array<Record<string, unknown>>;
};

export type AudienceHypotheses = {
  analysis_id: string;
  hypotheses: Array<{
    statement: string;
    evidence: Array<{ source: string; observation: string; status: string }>;
    artist_context: string[];
    uncertainty: string;
    validation_experiment: string;
  }>;
  limitations: string[];
};

export type ReleasePlanTask = {
  task_id: string;
  stage: "pre_release" | "release_day" | "post_release";
  title: string;
  action: string;
  day_offset: number;
  planned_date: string | null;
  depends_on: string[];
};

export type ReleasePlan = {
  plan_id: string;
  song_id: string;
  analysis_id: string | null;
  release_date: string | null;
  goal: string | null;
  status: "draft" | "approved";
  tasks: ReleasePlanTask[];
  limitations: string[];
  created_at: string;
  updated_at: string;
  approved_at: string | null;
};

export type ReleasePlanList = { items: ReleasePlan[] };

export type VideoRender = {
  render_id: string;
  song_id: string;
  asset_id: string;
  job_id: string;
  render_format: "music_visualizer" | "full_music_video";
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string;
  progress_percent: number;
  error: { code: string; message: string } | null;
  scene_plan: Array<{
    name: "opening_title" | "audio_reactive" | "closing_card";
    start_seconds: number;
    end_seconds: number;
    transition: "fade" | "cut";
  }>;
  provenance: Record<string, unknown>;
  output_metadata: Record<string, unknown> | null;
  output_size_bytes: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  status_url: string;
  download_url: string | null;
};

export type VideoRenderList = { items: VideoRender[] };

export type EvidenceClaim = {
  claim: string;
  evidence_refs: string[];
  kind: "observed" | "measured" | "predicted" | "interpretation" | "recommendation";
};

export type ARReport = {
  report_id: string;
  analysis_id: string;
  schema_version: string;
  provider: string;
  model: string | null;
  prompt_version: string;
  created_at: string;
  summary: string;
  strengths: EvidenceClaim[];
  improvement_opportunities: EvidenceClaim[];
  hook_candidates: EvidenceClaim[];
  recommendations: EvidenceClaim[];
  limitations: string[];
  disclaimer: string;
};

export type AgentPipeline = {
  analysis_id: string;
  song_id: string;
  generated_at: string;
  limitations: string[];
  results: {
    logs: string[];
    song_intelligence: {
      bpm: number;
      musical_key: string;
      energy: number;
      valence: number;
      mood: string;
      structure: string[];
      hooks: string[];
      lyrical_themes: string[];
      production_notes: string[];
      a_r_insights: string[];
    };
    audience: {
      primary_segment: string;
      summary: string;
      segments: Array<{
        name: string;
        description: string;
        age_range: string;
        interests: string[];
        platform_affinity: Record<string, number>;
        match_score: number;
      }>;
    };
    content_plan: {
      pieces: Array<{
        format: string;
        hook: string;
        concept: string;
        caption: string;
        cta: string;
        sound_strategy: string;
      }>;
      posting_cadence: string;
      overarching_angle: string;
    };
    marketing_strategy: {
      release_type: string;
      timeline_weeks: number;
      phases: Record<string, string[]>;
      platform_priority: string[];
      budget_allocation: Record<string, number>;
      pitch_targets: string[];
      key_message: string;
    };
    optimization: {
      metrics: {
        streams: number;
        saves: number;
        playlist_adds: number;
        social_views: number;
        engagement_rate: number;
        follower_delta: number;
        score: number;
      };
      what_worked: string[];
      what_underperformed: string[];
      recommendations: string[];
      lessons_learned: string[];
    };
    final: {
      orchestrator_summary: string;
      top_priority_actions: string[];
    };
  };
};

export type Capabilities = {
  api_version: string;
  capabilities: {
    song_upload: boolean;
    audio_analysis: boolean;
    librosa_features: boolean;
    essentia_features: boolean;
    mock_ai_report: boolean;
    openrouter_report: boolean;
    social_publishing: boolean;
    music_distribution: boolean;
    paid_campaign_execution: boolean;
    music_visualizer_render: boolean;
    full_music_video_render: boolean;
    youtube_connection: boolean;
    instagram_connection: boolean;
    facebook_connection: boolean;
  };
};
