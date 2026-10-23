# AI Music Marketer

## Complete Product and System Specification

**Version:** 1.0\
**Status:** Proposed complete specification for review and sharing\
**Purpose:** Define what AI Music Marketer is, who it serves, how it
should behave, how its components coordinate, and how it will be built
safely and incrementally. This document is a product and system
specification, not an implementation prompt.

------------------------------------------------------------------------

## 1. Executive summary

AI Music Marketer is an AI-powered music management and marketing
platform for independent musicians. It helps artists understand their
songs, make informed creative and release decisions, develop promotional
content, reach relevant audiences, coordinate campaigns, measure
outcomes, and improve future decisions.

The product aims to make capabilities commonly provided by larger music
teams more accessible to independent artists. It combines specialist
music-analysis tools, five bounded AI agents, an orchestrator,
authorized third-party integrations, and eventually proprietary models
trained on suitable, permissioned performance data.

The product must be honest about uncertainty. It cannot guarantee that a
song will go viral, become popular, earn a particular amount, or be
recommended by a streaming service. It can analyze evidence, generate
hypotheses, propose experiments, help execute approved work, and measure
results where data access permits.

### Product principle

**Measure what can be measured. Label what is predicted. Explain
recommendations. Execute external actions only with authorization. Learn
from real outcomes.**

------------------------------------------------------------------------

## 2. Vision, mission, and target users

### Vision

Give independent artists access to coordinated, data-informed music
management and marketing tools without making success depend on having a
large marketing budget.

### Mission

Turn a song, artist context, and release goal into an evidence-based
plan that helps an artist prepare, promote, measure, and improve a music
release.

### Primary users

-   Independent musicians and singers.
-   Songwriters and producers releasing their own work.
-   Emerging artists without a dedicated marketing team.
-   Artist managers working with independent artists.
-   Eventually, labels and small music teams managing multiple artists.

### Core user problem

Artists often know how to create music but may lack direction on
positioning, content creation, release planning, distribution, audience
development, campaign measurement, and interpreting performance data.

### Product promise

AI Music Marketer acts as a coordinated digital music-management
assistant. It helps the artist decide what to do, explains why, prepares
the necessary materials, and performs supported actions only when the
artist has authorized them.

------------------------------------------------------------------------

## 3. Product objectives

1.  Accept a song and optional lyrics, artwork, artist information,
    release goals, and video assets.
2.  Extract objective audio measurements and model-derived musical
    descriptions.
3.  Store a versioned, structured Song Intelligence record.
4.  Generate constructive, candid A&R-style feedback tied to evidence.
5.  Produce testable audience hypotheses rather than unsupported
    demographic claims.
6.  Generate pre-release, release-day, and post-release plans.
7.  Suggest short-form videos, Reels, Shorts, lyric videos, performance
    clips, captions, and calls to action.
8.  Help prepare and edit promotional assets, with review before
    publication.
9.  Integrate with authorized music, social, advertising, distribution,
    and analytics providers when access exists.
10. Measure campaign performance and recommend evidence-based
    adjustments.
11. Build a lawful, consent-aware foundation for future proprietary ML.
12. Keep subscription access separate from artistic merit and organic
    opportunity scoring.

## 4. Non-goals and prohibited promises

The platform must not claim to: - guarantee virality, streams,
followers, revenue, or playlist placement; - objectively determine
universal artistic quality with one number; - know a platform's private
recommendation algorithm; - upload music to every service without a
legitimate distribution path; - publish to every social network without
supported API permissions; - scrape private data or bypass platform
restrictions; - train on uploaded music without the required rights and
consent; - spend money, publish, distribute, or make other consequential
changes without explicit authorization; - fabricate missing metrics,
lyrics, confidence scores, or audience facts.

The first product milestone is deliberately smaller than the full
vision: **song upload → audio analysis → structured Song Intelligence →
AI-generated A&R report**.

------------------------------------------------------------------------

## 5. Product principles

### 5.1 Fair access

Artists on the same subscription tier should receive the same core
analysis process and decision criteria. Subscription price must not
secretly influence artistic merit or organic opportunity ranking.

Paid promotion is distinct from organic visibility. Advertising budgets,
spend, targeting, and outcomes must be shown transparently. The platform
cannot promise equal ad reach when ad auctions, targeting, geography,
and competition differ.

### 5.2 Honest, constructive feedback

Feedback should identify strengths, weaknesses, risks, and practical
improvements. It should be specific and respectful, referencing
timestamps, supplied lyrics, measured characteristics, or clearly
labeled interpretations when possible.

### 5.3 Evidence and uncertainty

All outputs must distinguish: - **Observed:** supplied by the artist or
reported by an authorized source. - **Measured/derived:** computed from
audio or other input data. - **Predicted:** generated by a model. -
**Interpreted:** an explanation based on available evidence. -
**Recommended:** a proposed action. - **Executed:** an action confirmed
by a provider. - **Unknown:** not available or not sufficiently
supported.

### 5.4 Human control

Require explicit, scoped approval before public publishing, release
submission, advertising spend, account-changing operations, or
destructive data actions.

### 5.5 Modularity

Every analyzer, AI provider, integration, and agent should be
replaceable behind stable interfaces.

### 5.6 Privacy and rights

Unreleased music is sensitive intellectual property. Keep assets private
by default, minimize third-party data sharing, and distinguish
processing consent from model-training consent.

------------------------------------------------------------------------

## 6. End-to-end user journey

1.  The artist creates an account and artist profile.
2.  The artist creates a song record and uploads a private audio file.
3.  The artist may supply lyrics, language, genre/style preferences,
    release goals, artwork, and existing video footage.
4.  The platform validates the file, records the asset, and queues
    analysis.
5.  The audio pipeline extracts features and candidate musical sections.
6.  The lyrics pipeline analyzes lyrics only when supplied or separately
    transcribed with clear uncertainty.
7.  The system builds a versioned Song Intelligence object.
8.  The AI reasoning layer generates an A&R report, clearly separating
    evidence from predictions.
9.  The artist reviews the report and may correct metadata or provide
    feedback.
10. In later phases, the orchestrator invokes audience, content, and
    marketing agents to create a draft release plan.
11. The artist approves, edits, or rejects suggestions.
12. Supported integrations execute approved actions.
13. The analytics agent evaluates authorized results and recommends next
    experiments.

------------------------------------------------------------------------

## 7. System architecture

### 7.1 Chosen architecture direction

The selected direction is a **modular monolith with background
workers**. The core backend remains one deployable application with
clear internal modules. Long-running audio analysis, video rendering,
provider synchronization, and other expensive work runs asynchronously.

Do not start with a large microservices fleet. A module may be extracted
later if scale, fault isolation, team ownership, or deployment needs
justify it.

### 7.2 Logical architecture

``` text
Artist Web Application
        |
        v
Backend API / Identity / Authorization
        |
        +---- PostgreSQL: business data, versions, jobs, metrics
        +---- Private Object Storage: audio, video, artwork, exports
        +---- Queue + Background Workers: analysis, rendering, sync
        |
        +---- Song Intelligence Module
        |       +-- File validation and FFmpeg
        |       +-- Essentia and Librosa
        |       +-- Selected pretrained audio models
        |       +-- Lyrics analysis
        |       +-- Canonical Song Intelligence
        |
        +---- Agent Orchestration Module
        |       +-- Music Analysis Agent
        |       +-- Audience Intelligence Agent
        |       +-- Content Strategy Agent
        |       +-- Marketing Strategy Agent
        |       +-- Analytics & Optimization Agent
        |
        +---- AI Gateway
        |       +-- OpenRouter adapter initially
        |       +-- Internal provider interface
        |
        +---- Integration Module
        |       +-- Streaming/analytics
        |       +-- Social publishing/analytics
        |       +-- Distribution
        |       +-- Advertising
        |       +-- Payments (later)
        |
        +---- Consent, Rights, Audit, Observability
```

### 7.3 Proposed technology defaults

These are the selected/proposed starting technologies, subject to
repository inspection and compatibility review: - Frontend: Next.js,
React, TypeScript, Tailwind CSS. - Backend: Python and FastAPI. -
Database: PostgreSQL, SQLAlchemy, Alembic. - Background jobs: Redis and
Celery, or a suitable equivalent if the existing repository already uses
one. - Media: FFmpeg. - Audio analysis: Essentia and Librosa. - ML
inference: PyTorch/torchaudio and selected pretrained models. - AI
reasoning: OpenRouter through a provider abstraction. - Storage: private
S3-compatible object storage, with a local development adapter. -
Development environment: Docker and Docker Compose. - Testing: pytest,
API contract tests, frontend tests, integration tests, and end-to-end
tests.

The implementation agent must inspect existing work and reuse it rather
than recreating infrastructure.

------------------------------------------------------------------------

## 8. Multi-agent architecture

The project will use **five specialist agents plus one orchestrator**.
Agents are bounded roles with typed inputs and outputs, not unrestricted
chatbots.

### 8.1 Orchestrator

Responsibilities: - identify the task and required workflow; - check
permissions, prerequisites, and data freshness; - invoke only the
necessary agents; - pass versioned structured inputs; - validate outputs
and handle bounded retries; - reconcile conflicts and preserve
uncertainty; - assemble the final response or plan; - enforce approval
gates; - record model, prompt, tool, cost, and output versions.

The orchestrator must not invent measurements or allow unbounded
agent-to-agent loops.

### 8.2 Music Analysis Agent

**Purpose:** Interpret specialized audio and lyrics analysis and provide
evidence-based A&R feedback.

Inputs: audio-analysis outputs, audio asset reference when required by a
specialist tool, supplied lyrics, artist context.

Outputs: - Song Intelligence; - musical identity summary; - candidate
sections and hooks with timestamps; - strengths, weaknesses, and
limitations; - evidence-linked A&R report.

It must not invent lyrics, pretend an LLM measured BPM, or claim a
candidate hook is guaranteed to perform.

### 8.3 Audience Intelligence Agent

**Purpose:** Develop and test hypotheses about potentially relevant
listeners.

Inputs: Song Intelligence, artist goals, language/territory preferences,
authorized historical performance data.

Outputs: - primary and secondary audience hypotheses; - potentially
relevant communities, territories, contexts, and content preferences; -
supporting evidence and uncertainty; - suggested validation experiments.

It must not present speculative demographics as facts or claim access to
private platform recommendation logic.

### 8.4 Content Strategy Agent

**Purpose:** Turn song characteristics and audience hypotheses into
practical promotional content.

Inputs: Song Intelligence, audience hypotheses, artist preferences,
available assets, platform specifications.

Outputs: - Reels/Shorts and other supported content concepts; -
recommended timestamps and reasons; - shot lists, edit instructions,
captions, subtitles, and CTAs; - creative briefs and export
requirements; - draft content assets when generation/editing tools are
connected.

It must not publish without approval or use assets without appropriate
rights.

### 8.5 Marketing Strategy Agent

**Purpose:** Create staged release and campaign plans.

Inputs: song analysis, audience hypotheses, content plan, release date,
artist goals, budget and explicit permissions.

Outputs: - pre-release, release-day, and post-release schedule; - action
priorities, dependencies, costs, and uncertainty; - organic and optional
paid campaign proposals; - milestone metrics and experiment plans.

It must not spend money, promise reach, or assume distributor/social API
access exists.

### 8.6 Analytics & Optimization Agent

**Purpose:** Interpret authorized campaign and content results.

Inputs: provider metrics, time windows, exposure/spend context, prior
plans and predictions.

Outputs: - performance report; - comparisons against suitable
baselines; - data-quality warnings; - what appears to work and what is
uncertain; - recommended follow-up experiments; - outcome records for
future ML, subject to consent.

It must not fabricate metrics or claim causality without suitable
evidence.

### 8.7 Coordination workflow

``` text
User request
  -> Orchestrator checks scope and permissions
  -> Music Analysis Agent, if analysis is missing/stale
  -> Audience Intelligence Agent
  -> Content Strategy Agent
  -> Marketing Strategy Agent
  -> Human review and approval
  -> Authorized execution through integrations
  -> Analytics & Optimization Agent
  -> Orchestrator produces report and next steps
```

Independent tasks may run in parallel. Each run must record workflow ID,
agent, input/output schema versions, model/provider, prompt version,
timestamps, status, and errors. Use timeouts, bounded retries,
token/cost budgets, and allowlisted tools.

------------------------------------------------------------------------

## 9. Song Intelligence Engine

### 9.1 Pipeline

``` text
Upload
 -> file validation
 -> private object storage
 -> checksum and asset record
 -> FFmpeg decode/normalization
 -> Essentia and Librosa features
 -> optional pretrained audio models
 -> structure and hook candidates
 -> optional lyrics analysis
 -> schema validation and persistence
 -> compact structured context to AI gateway
 -> validated A&R report
```

### 9.2 Audio features

Potential features, subject to tool support and evaluation: - duration,
sample rate, channel count; - loudness measures and energy/RMS
profile; - tempo/BPM and beat positions; - key/mode estimates; -
spectral centroid, bandwidth, contrast, MFCC/chroma and related
descriptors; - rhythm, onset and timbral characteristics; -
model-predicted genre, mood, instrumentation, vocal/instrumental
characteristics, or embeddings when supported.

Do not calculate redundant features without a reason. For each feature
document its definition, unit, source, version, limitations, cost, and
downstream purpose.

### 9.3 Musical structure and hooks

Potential sections include intro, verse, pre-chorus, chorus, bridge,
instrumental, and outro. Use neutral section labels if the model cannot
reliably identify a role.

Hook candidates may be lyrical, melodic, rhythmic, instrumental, or
vocal. Store start/end timestamps, type, supporting evidence, and
confidence only when meaningful. A candidate hook is not proof of
commercial effectiveness.

### 9.4 Lyrics

Analyze lyrics supplied by the artist. Potential outputs include
language, themes, narrative, recurring phrases, emotional tone, and
candidate hook lines. If lyrics are absent, mark them unavailable. If
automatic transcription is later added, preserve transcription
confidence and allow correction.

### 9.5 Canonical Song Intelligence schema

Illustrative structure:

``` json
{
  "song_id": "uuid",
  "analysis_id": "uuid",
  "schema_version": "1.0",
  "analysis_version": "1.0",
  "audio_features": {
    "tempo_bpm": {
      "value": 124.0,
      "status": "estimated",
      "unit": "bpm",
      "source": "essentia"
    },
    "key": {
      "value": "A",
      "status": "estimated",
      "source": "selected-model"
    }
  },
  "sections": [],
  "hook_candidates": [],
  "lyrics_analysis": {
    "available": false,
    "themes": [],
    "candidate_lines": []
  },
  "predictions": [],
  "limitations": [],
  "provenance": [],
  "created_at": "ISO-8601"
}
```

This is a conceptual example, not a finalized API contract.
Null/unavailable values must not be fabricated. Keep both conflicting
analyzer outputs when useful and document how a selected value was
chosen.

### 9.6 Versioning and provenance

Track: - analysis ID and schema version; - analyzer/library/model name
and version; - feature/configuration version; - prompt version and AI
model/provider; - timestamp and input asset checksum; - consent/rights
state relevant to use; - failure and limitation metadata.

Re-analysis creates a new version rather than silently overwriting the
historical result.

------------------------------------------------------------------------

## 10. AI reasoning and OpenRouter

### 10.1 Design

OpenRouter is the initial LLM gateway, not the proprietary intelligence
layer itself. Domain modules depend on an internal AI-provider
interface. This allows a future gateway, direct provider, or proprietary
model to replace the initial adapter.

### 10.2 AI responsibilities

The AI reasoning layer interprets structured Song Intelligence and
relevant artist context to generate: - A&R assessment; - strengths and
weaknesses; - audience hypotheses; - content ideas; - release and
marketing recommendations; - uncertainty and evidence references.

It should not calculate values better handled by audio tools, invent
data, or treat predictions as facts.

### 10.3 Provider requirements

-   configurable model ID and API key;
-   keys remain server-side;
-   request timeouts and bounded retries;
-   rate-limit and provider-error handling;
-   structured output validation;
-   cost/usage and latency logging;
-   optional fallback only when configured and quality-compatible;
-   safe error handling and redaction;
-   mock provider that works without network access or credentials.

### 10.4 Context and privacy

Send only relevant, permissioned, compact information. Avoid sending raw
audio/video to a text LLM when structured analysis is sufficient.
Disclose applicable third-party processing and respect the artist's
consent settings.

------------------------------------------------------------------------

## 11. Internal API design

All application endpoints should be versioned under `/api/v1`. Use HTTPS
and JSON for standard API calls, signed private upload URLs for large
media where appropriate, and asynchronous job resources for long-running
tasks.

### 11.1 API conventions

-   Authentication and authorization on every private resource.
-   UUIDs or another consistent opaque ID strategy.
-   ISO 8601 UTC timestamps.
-   Cursor pagination for growing collections.
-   Standard error envelope with stable error code and request ID.
-   Idempotency keys on retryable operations that cause side effects.
-   Documented rate limits and safe retry rules.
-   OpenAPI generated from actual FastAPI routes.
-   No secrets in URLs, frontend bundles, or logs.
-   Long-running work returns `202 Accepted` with a job/status URL.
-   Webhooks require signature verification, replay protection, and
    idempotent handling.
-   Never expose hidden chain-of-thought; provide concise rationale and
    evidence instead.

Example error:

``` json
{
  "error": {
    "code": "AUDIO_FORMAT_UNSUPPORTED",
    "message": "The uploaded file could not be processed as a supported audio format.",
    "request_id": "uuid",
    "details": []
  }
}
```

### 11.2 Proposed endpoint inventory

These endpoints define the planned API surface. They should be
implemented only when the corresponding phase is approved.

**Health and capabilities** - `GET /api/v1/health` -
`GET /api/v1/ready` - `GET /api/v1/capabilities`

**Songs and assets** - `POST /api/v1/songs` -
`GET /api/v1/songs/{song_id}` - `PATCH /api/v1/songs/{song_id}` -
`POST /api/v1/songs/{song_id}/assets/upload-intent` -
`POST /api/v1/songs/{song_id}/assets/complete` -
`GET /api/v1/songs/{song_id}/assets` -
`DELETE /api/v1/assets/{asset_id}`

**Song Intelligence** - `POST /api/v1/songs/{song_id}/analyses` -
`GET /api/v1/analyses/{analysis_id}` -
`GET /api/v1/analyses/{analysis_id}/intelligence` -
`GET /api/v1/analyses/{analysis_id}/report` -
`POST /api/v1/analyses/{analysis_id}/reprocess`

**Agent workflows and reports** -
`POST /api/v1/workflows/music-marketing-plans` -
`GET /api/v1/workflows/{workflow_id}` -
`GET /api/v1/workflows/{workflow_id}/report` -
`POST /api/v1/reports/{report_id}/feedback`

**Release and content planning** - `POST /api/v1/release-plans` -
`GET /api/v1/release-plans/{plan_id}` -
`PATCH /api/v1/release-plans/{plan_id}` -
`POST /api/v1/release-plans/{plan_id}/approve` -
`POST /api/v1/content-plans` - `GET /api/v1/content-plans/{plan_id}` -
`POST /api/v1/content-assets` - `GET /api/v1/content-assets/{asset_id}`

**Campaigns** - `POST /api/v1/campaigns` -
`GET /api/v1/campaigns/{campaign_id}` -
`POST /api/v1/campaigns/{campaign_id}/approve` -
`POST /api/v1/campaigns/{campaign_id}/execute` -
`POST /api/v1/campaigns/{campaign_id}/pause` -
`GET /api/v1/campaigns/{campaign_id}/status`

**Analytics** - `POST /api/v1/integrations/{connection_id}/sync-jobs` -
`GET /api/v1/analytics/songs/{song_id}` -
`GET /api/v1/analytics/campaigns/{campaign_id}` -
`GET /api/v1/analytics/reports/{report_id}` -
`POST /api/v1/analytics/feedback`

**Integrations** - `GET /api/v1/integrations` -
`POST /api/v1/integrations/{provider}/connect` -
`GET /api/v1/integrations/{provider}/callback` -
`DELETE /api/v1/integrations/{connection_id}` -
`GET /api/v1/integrations/{connection_id}/capabilities` -
`POST /api/v1/webhooks/{provider}`

**Consent, rights, and privacy** - `GET /api/v1/consents` -
`POST /api/v1/consents` -
`POST /api/v1/consents/{consent_id}/withdraw` -
`POST /api/v1/rights/declarations` -
`POST /api/v1/privacy/data-export-requests` -
`POST /api/v1/privacy/deletion-requests`

**Jobs and audit** - `GET /api/v1/jobs/{job_id}` -
`POST /api/v1/jobs/{job_id}/cancel` - `GET /api/v1/audit-events`
(restricted role only)

### 11.3 Example analysis request

``` http
POST /api/v1/songs/{song_id}/analyses
Idempotency-Key: <unique-client-key>
Content-Type: application/json
```

``` json
{
  "asset_id": "uuid",
  "lyrics_asset_id": null,
  "analysis_profile": "standard_v1",
  "include_pretrained_predictions": true,
  "generate_ai_report": true
}
```

Response:

``` json
{
  "analysis_id": "uuid",
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/v1/analyses/uuid",
  "requested_at": "ISO-8601"
}
```

The server must validate asset ownership and status. It must not trust
an asset ID merely because the client supplied it.

------------------------------------------------------------------------

## 12. External API and integration architecture

Integrations are capability-constrained. Do not promise an integration
feature until current official documentation, permissions, app-review
status, territory/account limitations, and commercial terms have been
checked.

### 12.1 OpenRouter

Used for AI reasoning over structured inputs. Configure models and keys
through server-side environment/secrets management. Record
model/provider, usage, latency, errors, and prompt version.

### 12.2 Audio and ML tools

-   FFmpeg for decoding, normalization, trimming, and media operations.
-   Essentia and Librosa for music/audio analysis.
-   PyTorch, torchaudio, or selected Hugging Face models for supported
    inference tasks.

Verify licenses, commercial-use terms, model cards, hosting
requirements, and performance before production use.

### 12.3 Streaming and music services

Potential targets include Spotify, Apple Music, YouTube/YouTube Music,
Amazon Music, and regional services such as JioSaavn. Their APIs do not
necessarily provide the same catalog, analytics, or audience
capabilities.

Rules: - use official APIs or authorized providers; - do not assume
private stream counts or demographics are available; - preserve provider
metric name, definition, source, reporting window, and retrieval
timestamp; - do not scrape or bypass access controls; - use
artist-provided reports or licensed data when a required metric is
unavailable.

### 12.4 Music distribution

Begin with evaluation of legitimate distributors or distribution
partners and their documented APIs/agreements. Do not assume a
distributor offers unrestricted API access.

A distribution workflow needs rights/ownership declarations, metadata
and contributor credits, audio/artwork validation, release date and
territory choices, submission state, rejection/correction handling, and
audit records.

If no approved API is available, provide a release-ready package and
guided manual workflow. Do not claim automatic delivery until end-to-end
access has been verified.

### 12.5 Social publishing and analytics

Initial social publishing targets are **YouTube, Instagram, and Facebook
only**. Do not add TikTok or other social platforms to the initial
integration scope. Build a capability matrix for each selected provider:
account requirements, OAuth scopes, reading analytics, publishing,
scheduling, comments, advertising, review requirements, rate limits,
regions, and account-type limitations. Enable only capabilities actually
granted to the connected account; provider permissions and app-review
requirements must be verified before claiming a publishing action is
available.

Enable only capabilities actually granted to the connected account.
Where publishing is unsupported, provide export/manual publishing
assistance.

### 12.6 Advertising

Paid campaign execution is opt-in and separate from organic
recommendations. Require an authorized ad account, explicit
objective/target/date/budget approval, hard budget ceilings, pause/stop
controls, spend reconciliation, and audit logs. Never guarantee
outcomes.

### 12.7 Video tools

Initial finished-video formats are limited to (1) music visualizers and
(2) full music videos. The artist receives a completed MP4; the product
is not an editor that requires the artist to assemble the video
manually.

**Music visualizer pipeline:** accept an authorized song asset, artwork,
and metadata; derive audio-reactive measurements; compose waveform or
frequency visuals, motion, transitions, and titles; synchronize the
original audio; render and validate the MP4.

**Full music-video pipeline:** create a structured scene plan from song
context and an approved creative brief; obtain visuals from artist-owned
assets, rights-cleared sources, deterministic graphics, and/or optional
local generative models; assemble scenes and transitions against the
song; render and validate a complete MP4. AI-generated cinematic footage
is an optional capability, not a prerequisite for the first renderer. If
no suitable local model is available, the system must use permitted
assets and clearly disclose the visual-generation mode rather than
pretending it generated cinematic footage.

**Rendering architecture:** keep planning, asset generation, timeline
composition, rendering, and validation behind replaceable module
interfaces. Use background jobs for rendering; keep originals immutable;
store generated assets and output privately; record source/provenance,
model and version where applicable, licensing/rights declarations,
render settings, and job status. Use FFmpeg for media assembly/export,
Python for orchestration, and Pillow or equivalent open-source tooling
for graphics. Run a validation pass for file integrity, codecs,
duration, resolution/aspect ratio, audio presence/synchronization, and
expected output asset metadata.

Prefer free/open-source tools and local execution. No paid video API is
required by the baseline. Local generative video models must be
benchmarked for quality, speed, memory fit, commercial-use license, and
the teammate's RTX 4060 8 GB VRAM before being selected. Do not promise
that every model will run on that hardware or that unlimited cinematic
generation is possible at zero cost.

### 12.8 Payments

Subscription and billing integration can be implemented in a later
phase. Verify billing webhooks, make processing idempotent, and keep
subscription entitlements separate from artistic merit and organic
ranking.

### 12.9 Integration registry

Track provider/API version, capabilities, scopes, account requirements,
region restrictions, review status, token expiry/revocation, rate
limits, last successful sync, and terms/license review date.

------------------------------------------------------------------------

## 13. Database and data model

PostgreSQL is the proposed transactional source of truth. Large media
files belong in private object storage. Redis is for queue/cache
coordination, not the only durable record of important business state.

### 13.1 Core entities

**Identity:** `users`, `artist_profiles`, optional `organizations`,
`memberships`, `roles`.

**Catalog/assets:** `songs`, `media_assets`, optional
`song_contributors`, `rights_declarations`, `consent_records`.

**Analysis:** `song_analyses`, `analysis_jobs`, `audio_features`,
`song_sections`, `hook_candidates`, `lyrics_analyses`, `ai_reports`,
`model_versions`, `prompt_versions`.

**Agent workflow:** `workflow_runs`, `agent_runs`, `agent_artifacts`,
`approval_requests`, `audit_events`.

**Release/content:** `release_plans`, `content_plans`, `content_assets`,
`publishing_jobs`.

**Campaign/analytics:** `campaigns`, `campaign_actions`,
`campaign_approvals`, `metric_observations`, `campaign_reports`,
optional `experiment_assignments`.

**Integrations/billing:** `provider_connections`, `provider_sync_jobs`,
`provider_webhook_events`, `subscription_records`, `billing_events`.

**Privacy:** `data_export_requests`, `deletion_requests`,
`retention_records`.

### 13.2 Data rules

-   Use foreign keys, constraints, and indexes based on access patterns.
-   Store provider IDs beside internal IDs.
-   Store metrics with platform, metric name, unit, time window,
    timezone, retrieval time, and source.
-   Keep analysis results versioned; re-analysis creates a new record.
-   Use typed columns/tables for frequently queried data and JSONB for
    evolving payloads.
-   Encrypt or securely manage provider tokens; never log them.
-   Minimize collected personal data.
-   Support deletion/export and retention rules.
-   Do not put all future data into one unvalidated JSON blob.

### 13.3 ML lineage

Every training example should trace to its source asset and analysis
version, model/feature versions, consent and rights state, outcome
definition, platform/time window, exposure/spend context, inclusion
decision, and dataset snapshot/split.

------------------------------------------------------------------------

## 14. Background processing and job states

Audio analysis, video rendering, external sync, and AI report generation
should be asynchronous.

Suggested states: `queued → running → succeeded | failed | cancelled`

Optional states include `retry_wait` and `needs_approval`.

Every job records owner/tenant, task type, input versions, attempt
count, timestamps, progress stage, safe error code, retry policy,
idempotency key, and cancellation support where safe.

Distinguish internal acceptance from external completion. For example, a
release may be requested, submitted, accepted, distributed, rejected, or
unknown depending on verified provider status.

------------------------------------------------------------------------

## 15. Security, privacy, rights, and governance

### Authentication and authorization

-   Enforce ownership/role checks for every private resource.
-   Use short-lived signed URLs for private media.
-   Apply least privilege to workers and credentials.
-   Separate development, staging, and production credentials.
-   Require stronger controls for privileged administrative operations.

### Media security

-   Validate by decoding, not extension alone.
-   Enforce file size/duration limits.
-   Protect against path traversal, malicious media, and resource
    exhaustion.
-   Run media tools with restricted privileges and time/resource limits.
-   Keep originals private and derived artifacts separate.
-   Clean temporary files.

### Secrets

-   Keep API keys out of source control, prompts, frontend bundles,
    logs, and error responses.
-   Use environment configuration locally and managed secrets in
    production.
-   Support rotation/revocation.

### Rights and consent

Record separate consent/permissions for: - processing uploaded music; -
sending relevant data to third-party AI providers; - storing derived
analysis; - generating promotional assets; - publishing/scheduling
content; - connecting platform accounts; - aggregate analytics; -
training proprietary models.

Upload permission does not automatically imply model-training
permission. Provide data export and deletion workflows and document
retention.

### Auditability

Record who approved an external action, its exact scope/budget, provider
response, timestamp, and resulting state. Do not log raw audio or full
lyrics by default.

------------------------------------------------------------------------

## 16. Analytics, fairness, and optimization

### Metric comparability

Platform metrics differ in definitions. Preserve the source metric and
its definition/version. Do not treat a "view" on every platform as
identical.

### Context-aware evaluation

Where available, analyze retention, completion, shares, saves,
meaningful engagement, profile visits, click-through, listener
conversion, follower growth, and revenue. Interpret these against
suitable baselines and exposure.

### Causality

Use "associated with" unless evidence supports a causal claim. Consider
paid exposure, content format, artist baseline, timing, and platform
differences.

### Fairness

-   Subscription tier is excluded from artistic merit and organic
    opportunity scores.
-   Paid promotion is labeled and modeled separately.
-   Low exposure is not proof of low artistic quality.
-   Evaluate exposure bias, survivorship bias, genre/language coverage,
    and feedback loops.
-   Provide explanations and correction/appeal routes for high-impact
    decisions.

------------------------------------------------------------------------

## 17. Proprietary ML strategy

Do not train a large proprietary model from scratch at the beginning.

### Stage A: initial features and pretrained models

Build deterministic analysis and selected pretrained inference. Record
versions and limitations.

### Stage B: lawful outcomes

Collect authorized performance and campaign outcomes with consent,
source, time window, exposure, and context.

### Stage C: baseline predictive models

When suitable labeled data exists, evaluate interpretable baselines for
content performance, audience-hypothesis ranking, hook/content candidate
ranking, and campaign recommendation ranking.

### Stage D: evaluation

Use time-based splits and artist-level grouping where appropriate.
Prevent leakage from future outcomes. Evaluate calibration, ranking
quality, subgroup performance, and drift.

### Stage E: governance

Record model version, training data snapshot, evaluation results,
limitations, rollback plan, and retraining criteria. Respect consent
withdrawal and deletion requirements.

------------------------------------------------------------------------

## 18. Testing and quality standards

### Testing layers

-   Unit tests for schemas, analyzers, permissions, metric
    normalization, and state transitions.
-   API contract tests and provider adapter tests.
-   Integration tests with mocked external providers.
-   End-to-end tests from upload through report.
-   Security tests for authorization, upload handling, webhook
    verification, and secrets.
-   Regression tests on properly licensed sample audio.
-   Model evaluations on a rights-cleared dataset.

### Quality gate

A module is not complete merely because code exists. It must have
documented behavior, typed contracts, authorization checks, error/retry
handling, tests, logging/metrics, configuration docs, no committed
secrets, passing CI, reviewed migrations, and evidence that acceptance
criteria pass.

------------------------------------------------------------------------

## 19. Implementation roadmap

The existing repository roadmap and phase numbering should be inspected
before final phase mapping. The following is a recommended sequence, not
a claim that prior phases are complete.

1.  **Foundation:** repository assessment, architecture, configuration,
    database migrations, CI, logging, security baseline, provider
    interfaces.
2.  **Artist platform:** identity, profiles, authorization, onboarding,
    minimal dashboard.
3.  **Media:** song catalog, private upload, validation, storage, rights
    declarations, async jobs.
4.  **Song Intelligence:** FFmpeg, Essentia, Librosa, selected
    pretrained models, lyrics analysis, structure/hooks,
    schema/provenance, OpenRouter report, tests.
5.  **Audience Intelligence:** hypotheses, artist context, evidence and
    uncertainty.
6.  **Release and marketing planner:** release stages, content calendar,
    goals, draft plans, approvals.
7.  **Content/video:** creative briefs, editing, rendering, export,
    asset review.
8.  **Distribution/social integrations:** provider capability registry
    and authorized connections; only supported capabilities.
9.  **Campaign automation:** approved actions, budgets, idempotent
    execution, provider states, pause/stop, audit trail.
10. **Merit/growth:** exposure-aware baselines, fairness checks,
    explanations and appeals.
11. **Analytics/revenue/career intelligence:** authorized metric
    ingestion, reports, career history, conversion/revenue where
    available.
12. **Production readiness:** load tests, recovery, observability,
    security/privacy review, cost controls, incident procedures, model
    governance, launch checklist.

Do not implement future phases merely because they are described here.

------------------------------------------------------------------------

## 20. First milestone: song-upload-to-A&R-report vertical slice

The first implementation milestone must demonstrate one complete path:

1.  An authorized user creates a song record.
2.  They upload a private audio file.
3.  The backend validates the file, computes a checksum, stores it, and
    creates a processing job.
4.  FFmpeg creates a derived analysis copy without overwriting the
    original.
5.  Essentia and Librosa extract a documented initial feature set.
6.  The system persists a versioned Song Intelligence object with units,
    provenance, and uncertainty/unavailable statuses.
7.  A mock AI provider generates a schema-valid A&R report without
    external credentials.
8.  The OpenRouter adapter can be enabled through configuration with
    timeout, bounded retries, error handling, and usage logging.
9.  The user can view measurements, predictions, limitations, and the
    A&R report.
10. Automated tests cover permissions, invalid/corrupt files, job
    failures, schema validation, and core API contracts.
11. Documentation and CI checks pass.

This milestone is not the entire platform. It validates the core
architecture before expanding into the other agents.

------------------------------------------------------------------------

## 21. Coding-agent workflow and constraints

The implementation agent must: 1. Inspect the repository and existing
phase documentation. 2. Identify existing functionality before changing
files. 3. Report gaps against this specification. 4. Propose a small,
phase-bounded plan and list files to change. 5. Request approval for
architecture changes, database migrations, external services, and paid
API usage. 6. Implement one module at a time. 7. Add tests and
documentation alongside the code. 8. Run lint, type checks, tests, and
safe migration checks. 9. Report files changed, commands run, test
results, limitations, and remaining work. 10. Never claim an integration
works without verified testing or documented manual validation.

The agent must not rewrite the repository from scratch, silently change
architecture, deploy to production, run destructive production
migrations, connect external accounts, spend money, publish content, or
commit secrets without explicit authorization.

------------------------------------------------------------------------

## 22. Confirmed owner decisions

The owner has selected these decisions:

1.  **Architecture:** modular monolith with background workers.
2.  **Agents:** five specialist agents plus one orchestrator.
3.  **AI gateway:** OpenRouter with provider abstraction.
4.  **External actions:** draft first; explicit approval before
    execution.
5.  **First milestone:** complete song-upload-to-A&R-report vertical
    slice.

### Proposed technical defaults to confirm

-   PostgreSQL as transactional source of truth.
-   Redis + Celery or a suitable existing queue/worker solution.
-   Private object storage for media.
-   FFmpeg + Essentia + Librosa for the initial analysis pipeline.
-   Selected pretrained models only after license, commercial-use,
    quality, hosting, and input requirements are reviewed.
-   FastAPI versioned REST APIs and generated OpenAPI documentation.
-   Inspect and extend the existing repository instead of starting from
    zero.

------------------------------------------------------------------------

## 23. Final approval checklist

### Architecture

-   [x] Modular monolith + background workers.
-   [x] Five specialist agents + orchestrator.
-   [x] OpenRouter behind provider abstraction.
-   [x] Draft-first, approval-gated external actions.
-   [x] Song-upload-to-A&R-report as the first milestone.
-   [ ] Confirm PostgreSQL, queue/worker, object storage, and API
    defaults.
-   [ ] Confirm current repository and Phase 1 work will be inspected
    before changes.

### Product and governance

-   [ ] Subscription tier excluded from merit/organic opportunity
    scoring.
-   [ ] Paid advertising is separate from organic recommendations and
    requires budget approval.
-   [ ] Training on uploaded music requires appropriate rights and
    consent.
-   [ ] Observations, predictions, interpretations, and recommendations
    are distinguished.
-   [ ] Export, deletion, retention, audit, and third-party AI
    processing are documented.

### APIs and integrations

-   [ ] Every endpoint has a schema, authorization rule, error contract,
    and tests.
-   [ ] Long-running tasks use asynchronous jobs/status resources.
-   [ ] Side-effecting operations are idempotent and safely retryable.
-   [ ] Provider permissions and capabilities are verified before being
    promised.
-   [ ] No universal distribution/social-publishing claim is made
    without verified access.
-   [ ] API keys/tokens remain server-side and are never logged.

### First milestone

-   [ ] Private upload, validation, checksum, and job state transitions
    work.
-   [ ] FFmpeg normalization and initial audio features work.
-   [ ] Versioned Song Intelligence persists with provenance and
    uncertainty.
-   [ ] Mock AI provider works offline.
-   [ ] OpenRouter adapter is configurable and handles failures safely.
-   [ ] Report UI displays evidence and limitations.
-   [ ] Automated tests, documentation, and CI pass.

### Release gate

-   [ ] Owner explicitly approves the remaining checklist.
-   [ ] Module-by-module implementation prompts are reviewed before
    coding.
-   [ ] No deployment, paid API use, public publishing, ad spend, or
    external account connection occurs without separate authorization.

------------------------------------------------------------------------

## 24. Glossary

-   **Agent:** a bounded software role using tools and/or an AI model to
    perform a defined task.
-   **Orchestrator:** coordinates agent tasks, validates outputs,
    handles dependencies, and assembles the final result.
-   **Song Intelligence:** canonical, versioned structured information
    about a song and its analysis.
-   **A&R:** artist-and-repertoire style assessment of musical identity,
    strengths, weaknesses, and opportunities.
-   **Provider adapter:** replaceable interface to an external API or
    model.
-   **Observed metric:** value reported by an authorized source with its
    definition and time window.
-   **Audience hypothesis:** testable estimate of who might respond to a
    song, not a verified demographic fact.
-   **Provenance:** information identifying the algorithm/model,
    version, input, and time behind an output.
-   **Idempotency:** repeating an operation does not duplicate its side
    effects.
-   **Vertical slice:** a small but complete user journey through the
    system.

------------------------------------------------------------------------

## Final status

This specification defines the proposed product and system architecture.
It does not assert that all features, integrations, model licenses, or
commercial API access currently exist. Provider capabilities and
licensing must be verified before implementation.

**Status: owner-selected architecture direction recorded; remaining
technical defaults and acceptance checklist await review. No
implementation or deployment is authorized by this document.**

After approval, the next deliverables should be: 1. A separate detailed
API specification with request/response schemas and error contracts. 2.
A Markdown file containing 15 ordered modular implementation prompts. 3.
A detailed Song Intelligence specification if it is kept separate from
the master document.

------------------------------------------------------------------------

## Approved scope clarification --- video formats and social targets

This section records the owner's latest scope decision and is to be read
alongside the existing specification. It does not replace or expand the
first implementation milestone.

### Locked initial video formats

1.  **Music visualizer:** fully rendered, synchronized MP4 based on the
    song, artwork, audio-reactive visuals, and metadata.
2.  **Full music video:** fully rendered MP4 assembled from a planned
    sequence of scenes and transitions. Local AI-generated scenes are
    optional and subject to hardware, quality, rights, and license
    tests.

Lyric videos, standalone promotional Reels/Shorts, and other video
formats are deferred. Do not silently add them to the initial scope.

### Locked initial social publishing targets

-   YouTube
-   Instagram
-   Facebook

This is a platform scope decision, not a guarantee that all publishing
features are immediately available. Each integration remains subject to
official API capabilities, account eligibility, permissions, app review,
quotas, and platform policy. Publishing requires explicit, scoped user
approval. Do not add TikTok or other platforms without a new owner
decision.

### Rendering and delivery baseline

-   Deliver completed MP4 files; no artist-side timeline editing is
    required.
-   Run rendering as an asynchronous background job with progress and
    failure states.
-   Keep uploaded originals immutable and generated outputs private by
    default.
-   Validate each output and retain provenance for assets and models.
-   Use free/open-source-first tools; paid APIs are optional and require
    separate approval.
-   The first milestone remains song upload → audio analysis → Song
    Intelligence → A&R report. Video generation is a later phase.
