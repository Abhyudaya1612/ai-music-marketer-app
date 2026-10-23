# AI Music Marketer --- API Specification

**Version:** 1.0\
**Status:** Proposed API contract for review\
**Companion documents:** `AI_Music_Marketer_Complete_Specification.md`
and `AI_Music_Marketer_15_Modular_Implementation_Prompts.md`\
**Purpose:** Define API conventions and the first implementation scope
for AI Music Marketer. This document does not authorize deployment, paid
API usage, external account connections, publishing, distribution
submissions, or advertising spend.

------------------------------------------------------------------------

## 1. API design principles

1.  All application REST endpoints use the `/api/v1` prefix.
2.  JSON is used for standard request and response bodies unless the
    endpoint explicitly handles media upload.
3.  All private resources require authentication and an authorization
    check.
4.  Use UUIDs or the repository's already-established opaque identifier
    convention.
5.  Use ISO 8601 timestamps in UTC.
6.  Long-running operations return `202 Accepted` with a job or status
    resource.
7.  Side-effecting operations should support idempotency where
    applicable.
8.  Return a consistent error envelope with a stable machine-readable
    error code and request ID.
9.  Generate OpenAPI documentation from actual FastAPI routes; do not
    maintain a contradictory hand-written contract.
10. Never expose secrets in URLs, frontend bundles, logs, or error
    responses.
11. Provider capabilities must be verified before the product claims an
    integration feature exists.
12. Public publishing, distribution, account changes, and paid
    advertising require explicit, scoped approval before execution.

**Scope note:** This document defines shared conventions and a detailed
first-slice API. The later-phase endpoints are an inventory for
planning; they must not be represented as implemented merely because
they appear here.

------------------------------------------------------------------------

## 2. First milestone and API scope

The first vertical slice is:

`Create song → upload private audio → request analysis → poll job/status → persist Song Intelligence → generate A&R report → view report`

### Required for the first milestone

-   `GET /api/v1/health`
-   `GET /api/v1/ready`
-   `GET /api/v1/capabilities`
-   `POST /api/v1/songs`
-   `GET /api/v1/songs/{song_id}`
-   `PATCH /api/v1/songs/{song_id}`
-   `POST /api/v1/songs/{song_id}/assets/upload-intent`
-   `POST /api/v1/songs/{song_id}/assets/complete`
-   `GET /api/v1/songs/{song_id}/assets`
-   `POST /api/v1/songs/{song_id}/analyses`
-   `GET /api/v1/analyses/{analysis_id}`
-   `GET /api/v1/analyses/{analysis_id}/intelligence`
-   `GET /api/v1/analyses/{analysis_id}/report`
-   `GET /api/v1/jobs/{job_id}`

The implementation may use a local private-storage adapter during
development. Upload-intent and completion contracts should hide the
storage implementation from the client.

### Not required in the first milestone

Agent marketing workflows, release plans, content generation, social
publishing, distribution, advertising, billing, production OAuth
connections, and proprietary model training.

------------------------------------------------------------------------

## 3. Common conventions

### 3.1 Authentication and authorization

The authentication mechanism must be selected after inspecting the
existing repository. Do not invent a new identity system if one already
exists.

For every private resource: - authenticate the caller; - verify
ownership or an explicitly granted role; - scope database queries to the
authorized user/tenant; - avoid revealing whether another user's private
resource exists; - authorize asset IDs supplied in request bodies, not
just the parent song ID.

Unauthenticated health endpoints may be permitted by deployment policy.
Readiness details should not expose secrets or internal infrastructure
credentials.

### 3.2 Headers

Common request headers:

``` http
Authorization: Bearer <access-token>
Content-Type: application/json
X-Request-ID: <optional-client-request-id>
```

For retryable side-effecting operations:

``` http
Idempotency-Key: <unique-operation-key>
```

Authentication header details depend on the approved auth
implementation. Never place access tokens or API keys in query
parameters.

### 3.3 Response conventions

-   Successful reads/updates: `200 OK`
-   Resource created: `201 Created`
-   Asynchronous work accepted: `202 Accepted`
-   Successful operation with no response body: `204 No Content`
-   Invalid request: `400 Bad Request` or `422 Unprocessable Entity`,
    used consistently
-   Missing/invalid authentication: `401 Unauthorized`
-   Authenticated but unauthorized: `403 Forbidden`, or `404 Not Found`
    where needed to avoid leaking resource existence
-   Resource not found: `404 Not Found`
-   State conflict: `409 Conflict`
-   Unsupported media type: `415 Unsupported Media Type`
-   Payload too large: `413 Payload Too Large`
-   Rate limit: `429 Too Many Requests`
-   Unexpected server error: `500 Internal Server Error`
-   Temporarily unavailable dependency: `503 Service Unavailable`

Use the framework's actual status behavior consistently and document
deviations.

### 3.4 Standard error envelope

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

Rules: - `code` is stable and intended for programmatic handling. -
`message` is safe for the user and does not reveal internals. -
`request_id` supports troubleshooting. - `details` may contain
field-level validation information but no secrets, stack traces, raw
media, or private data belonging to another user.

Suggested initial error codes: - `VALIDATION_ERROR` -
`AUTHENTICATION_REQUIRED` - `RESOURCE_NOT_FOUND` -
`RESOURCE_ACCESS_DENIED` - `IDEMPOTENCY_CONFLICT` -
`AUDIO_FORMAT_UNSUPPORTED` - `AUDIO_FILE_CORRUPT` -
`AUDIO_FILE_TOO_LARGE` - `AUDIO_DURATION_EXCEEDED` - `ASSET_NOT_READY` -
`ANALYSIS_ALREADY_RUNNING` - `ANALYSIS_FAILED` - `JOB_NOT_CANCELLABLE` -
`AI_PROVIDER_UNAVAILABLE` - `AI_OUTPUT_INVALID` - `RATE_LIMITED` -
`INTERNAL_ERROR`

### 3.5 Pagination

For collection endpoints, use cursor pagination when the collection can
grow:

``` json
{
  "items": [],
  "next_cursor": null
}
```

Document maximum page size and cursor behavior on each collection
endpoint. Do not introduce pagination complexity for small fixed-size
responses without a need.

### 3.6 Timestamps and IDs

-   Timestamps: ISO 8601 UTC, for example `2026-10-14T12:30:00Z`.
-   IDs: UUID or the repository's consistent opaque ID format.
-   Never assume a client-supplied ID is valid or authorized.

------------------------------------------------------------------------

## 4. Health and capabilities

### `GET /api/v1/health`

**Purpose:** Lightweight process health check.

Example response:

``` json
{
  "status": "ok"
}
```

Do not expose secrets, environment variables, connection strings, or
sensitive dependency diagnostics.

### `GET /api/v1/ready`

**Purpose:** Readiness check for dependencies required to serve
requests.

Example response:

``` json
{
  "status": "ready"
}
```

A not-ready response should use a non-success status and a safe, minimal
explanation. The exact dependency checks should match the application
architecture.

### `GET /api/v1/capabilities`

**Purpose:** Tell the client which capabilities are configured and
available. Do not use this endpoint to claim access that has not been
verified.

Example response:

``` json
{
  "api_version": "v1",
  "capabilities": {
    "song_upload": true,
    "audio_analysis": true,
    "mock_ai_report": true,
    "openrouter_report": false,
    "social_publishing": false,
    "music_distribution": false,
    "paid_campaign_execution": false
  }
}
```

Values above are illustrative for a local environment, not claims about
a deployed system. A capability should be enabled only when the relevant
implementation and configuration are available.

------------------------------------------------------------------------

## 5. Songs

### `POST /api/v1/songs`

**Purpose:** Create a song record.

Request:

``` json
{
  "title": "Working Title",
  "artist_name": "Artist Name",
  "language": "en",
  "genre_preferences": ["indie pop"],
  "release_goal": "Prepare a single for release"
}
```

Fields: - `title` (required string, bounded length) - `artist_name`
(optional string) - `language` (optional language tag/string; do not
infer if unknown) - `genre_preferences` (optional array of strings) -
`release_goal` (optional string)

Response: `201 Created`

``` json
{
  "song_id": "uuid",
  "title": "Working Title",
  "artist_name": "Artist Name",
  "created_at": "2026-10-14T12:30:00Z",
  "updated_at": "2026-10-14T12:30:00Z"
}
```

Authorization: authenticated user; associate the song with that user's
authorized artist workspace.

Validation: reject malformed payloads and enforce reasonable field
limits.

### `GET /api/v1/songs/{song_id}`

**Purpose:** Retrieve a song the caller is authorized to access.

Response: `200 OK`

``` json
{
  "song_id": "uuid",
  "title": "Working Title",
  "artist_name": "Artist Name",
  "language": "en",
  "genre_preferences": ["indie pop"],
  "release_goal": "Prepare a single for release",
  "created_at": "2026-10-14T12:30:00Z",
  "updated_at": "2026-10-14T12:30:00Z"
}
```

### `PATCH /api/v1/songs/{song_id}`

**Purpose:** Update editable song metadata.

Request may include only fields being changed:

``` json
{
  "title": "Updated Title",
  "release_goal": "Prepare a release campaign"
}
```

Response: `200 OK` with the updated resource.

Authorization: verify ownership. Do not permit the client to change
owner IDs, rights/consent state, analysis provenance, or system-managed
timestamps through this endpoint.

------------------------------------------------------------------------

## 6. Private asset upload

### `POST /api/v1/songs/{song_id}/assets/upload-intent`

**Purpose:** Start an upload for a private media asset.

Request:

``` json
{
  "filename": "demo.wav",
  "declared_content_type": "audio/wav",
  "size_bytes": 24576000,
  "asset_kind": "audio_original"
}
```

The declared type and filename are hints only; the server must validate
the actual content.

Response: `201 Created`

``` json
{
  "asset_id": "uuid",
  "upload_method": "PUT",
  "upload_url": "short-lived-private-upload-url",
  "required_headers": {},
  "expires_at": "2026-10-14T12:45:00Z"
}
```

The URL above is a placeholder. The actual upload mechanism may differ
for the local adapter. Do not return a public permanent URL. Upload
intents must be scoped to the authenticated user and song and expire.

Suggested validations: - accepted media category; - maximum file size; -
filename safety; - quota/rate limit if implemented; - parent song
ownership; - allowed upload state.

### `POST /api/v1/songs/{song_id}/assets/complete`

**Purpose:** Finalize an upload and start server-side verification.

Request:

``` json
{
  "asset_id": "uuid"
}
```

Response: `202 Accepted`

``` json
{
  "asset_id": "uuid",
  "status": "verifying",
  "job_id": "uuid",
  "status_url": "/api/v1/jobs/uuid"
}
```

The server must verify that the asset belongs to the authorized
song/user and that the upload actually exists. It must not trust client
assertions that the upload succeeded.

Verification includes content decoding, supported format, size/duration
constraints, checksum calculation, private storage metadata, and safe
failure handling. A validated asset becomes eligible for analysis; a
failed asset must not be treated as ready.

### `GET /api/v1/songs/{song_id}/assets`

**Purpose:** List the caller's assets for the song.

Response: `200 OK`

``` json
{
  "items": [
    {
      "asset_id": "uuid",
      "asset_kind": "audio_original",
      "status": "ready",
      "size_bytes": 24576000,
      "checksum_sha256": "hex-string",
      "created_at": "2026-10-14T12:30:00Z"
    }
  ],
  "next_cursor": null
}
```

Do not expose internal storage paths or credentials. Consider whether
exposing checksums to the UI is useful; the example is a contract
illustration.

### `DELETE /api/v1/assets/{asset_id}`

**Planned for a later approved scope.** Deletion must verify ownership,
define behavior for active jobs and dependent reports, audit the action,
and respect retention/legal constraints. Do not implement destructive
deletion without an approved lifecycle design.

------------------------------------------------------------------------

## 7. Requesting audio analysis

### `POST /api/v1/songs/{song_id}/analyses`

**Purpose:** Request a new analysis of a ready private audio asset.

Headers:

``` http
Idempotency-Key: <unique-client-key>
Content-Type: application/json
```

Request:

``` json
{
  "asset_id": "uuid",
  "lyrics_asset_id": null,
  "analysis_profile": "standard_v1",
  "include_pretrained_predictions": false,
  "generate_ai_report": true
}
```

Fields: - `asset_id` (required): ready audio asset belonging to this
song and caller. - `lyrics_asset_id` (optional): supplied lyrics asset,
if the lyrics workflow is implemented and authorized. -
`analysis_profile` (required or defaulted by server): versioned
configuration identifier. - `include_pretrained_predictions` (boolean):
only enable if selected models have passed required review and are
configured. - `generate_ai_report` (boolean): use configured provider; a
mock provider must be available for offline development.

Response: `202 Accepted`

``` json
{
  "analysis_id": "uuid",
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/v1/analyses/uuid",
  "requested_at": "2026-10-14T12:30:00Z"
}
```

Rules: - Verify song ownership and asset readiness/ownership. - Validate
the analysis profile against server-supported profiles. - Use
idempotency to prevent duplicate work on retries. - Apply rate limits
and resource quotas appropriate to the environment. - Do not start a job
for an asset that has not passed verification. - Record the asset
checksum and analysis configuration version. - Long-running work is
asynchronous.

Potential errors: - `404 RESOURCE_NOT_FOUND` - `409 ASSET_NOT_READY` -
`409 ANALYSIS_ALREADY_RUNNING` - `413 AUDIO_FILE_TOO_LARGE` -
`415 AUDIO_FORMAT_UNSUPPORTED` - `422 VALIDATION_ERROR` -
`429 RATE_LIMITED`

### `GET /api/v1/analyses/{analysis_id}`

**Purpose:** Retrieve analysis status and summary metadata.

Response while running:

``` json
{
  "analysis_id": "uuid",
  "song_id": "uuid",
  "status": "running",
  "stage": "feature_extraction",
  "progress_percent": null,
  "created_at": "2026-10-14T12:30:00Z",
  "updated_at": "2026-10-14T12:31:00Z",
  "error": null
}
```

Response after failure:

``` json
{
  "analysis_id": "uuid",
  "song_id": "uuid",
  "status": "failed",
  "stage": "report_generation",
  "progress_percent": null,
  "created_at": "2026-10-14T12:30:00Z",
  "updated_at": "2026-10-14T12:32:00Z",
  "error": {
    "code": "AI_PROVIDER_UNAVAILABLE",
    "message": "The report could not be generated with the configured provider."
  }
}
```

Progress percentage is optional and should remain `null` if it cannot be
estimated honestly. Never expose stack traces or provider secrets.

### `GET /api/v1/jobs/{job_id}`

**Purpose:** Retrieve authorized job status.

Example response:

``` json
{
  "job_id": "uuid",
  "task_type": "song_analysis",
  "status": "running",
  "stage": "audio_feature_extraction",
  "attempt": 1,
  "created_at": "2026-10-14T12:30:00Z",
  "updated_at": "2026-10-14T12:31:00Z",
  "started_at": "2026-10-14T12:30:05Z",
  "finished_at": null,
  "error": null
}
```

Suggested states: `queued`, `running`, `retry_wait`, `succeeded`,
`failed`, `cancelled`. The implemented state machine must document legal
transitions. Job access is owner-scoped.

------------------------------------------------------------------------

## 8. Song Intelligence response

### `GET /api/v1/analyses/{analysis_id}/intelligence`

**Purpose:** Retrieve the canonical versioned structured result.

Illustrative response:

``` json
{
  "analysis_id": "uuid",
  "song_id": "uuid",
  "schema_version": "1.0",
  "analysis_version": "1.0",
  "created_at": "2026-10-14T12:32:00Z",
  "audio_features": {
    "duration_seconds": {
      "value": 182.4,
      "status": "measured",
      "unit": "seconds",
      "source": "ffmpeg",
      "source_version": "configured-version"
    },
    "tempo_bpm": {
      "value": 124.0,
      "status": "estimated",
      "unit": "bpm",
      "source": "essentia",
      "source_version": "configured-version"
    },
    "key": {
      "value": null,
      "status": "unavailable",
      "unit": null,
      "source": "selected-analyzer",
      "source_version": "configured-version"
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
  "provenance": [
    {
      "component": "audio_pipeline",
      "version": "configured-version",
      "input_checksum_sha256": "hex-string"
    }
  ]
}
```

### Feature object conventions

Where appropriate, each feature should include: - `value` (nullable when
unavailable); - `status`, such as `measured`, `derived`, `estimated`,
`predicted`, or `unavailable`; - `unit` where meaningful; - source
tool/model; - source version; - optional confidence/uncertainty only
when defined and calibrated enough to be meaningful; - optional
explanation/limitations.

This is a proposed shape, not permission to invent confidence scores.
Final schemas should be implemented with typed models and versioned.

### Versioning rules

-   Re-analysis creates a new analysis/version record.
-   Historical reports must remain associated with the analysis version
    that generated them.
-   Do not silently overwrite old analysis results.
-   Preserve source checksum, analyzer/model versions, configuration,
    timestamp, and relevant consent state.
-   Do not present a predicted genre/mood or candidate hook as a
    verified fact.

------------------------------------------------------------------------

## 9. A&R report

### `GET /api/v1/analyses/{analysis_id}/report`

**Purpose:** Retrieve the validated A&R report for the selected
analysis.

Illustrative response:

``` json
{
  "report_id": "uuid",
  "analysis_id": "uuid",
  "schema_version": "1.0",
  "provider": "mock",
  "model": null,
  "prompt_version": "ar_report_v1",
  "created_at": "2026-10-14T12:33:00Z",
  "summary": "A concise, evidence-aware summary of the supplied song analysis.",
  "strengths": [
    {
      "claim": "The track maintains a consistent energy profile.",
      "evidence_refs": ["audio_features.energy_profile"],
      "kind": "interpretation"
    }
  ],
  "improvement_opportunities": [],
  "hook_candidates": [],
  "recommendations": [],
  "limitations": [
    "No listener performance data was provided, so audience response cannot be verified."
  ],
  "disclaimer": "This report is decision support, not a guarantee of commercial success."
}
```

The exact report schema should be agreed with the frontend before
implementation. Every evidence reference must point to available data.
Empty arrays are valid when the analysis cannot support a claim. The API
must not return hidden model reasoning; it may return concise rationales
and evidence references.

Potential errors: - `404 RESOURCE_NOT_FOUND` -
`409 ANALYSIS_NOT_COMPLETE` - `404 REPORT_NOT_AVAILABLE`

------------------------------------------------------------------------

## 10. Idempotency and retries

For operations that create work or could cause side effects: - accept an
`Idempotency-Key`; - scope the key to the authenticated actor and
operation; - persist the operation/result mapping for a documented
retention window; - same key + same effective request returns the
original result; - same key + materially different request returns
`409 IDEMPOTENCY_CONFLICT`; - do not retry a non-idempotent provider
action blindly; - use bounded retry policies with backoff for transient
failures; - distinguish a local request being accepted from a provider
action actually completing.

For the first milestone, idempotency is particularly important for
analysis creation and upload completion.

------------------------------------------------------------------------

## 11. Security and media constraints

-   Authenticate and authorize every private endpoint.
-   Verify ownership for both parent resources and supplied child IDs.
-   Use short-lived signed URLs for private media.
-   Validate media by decoding, not extension alone.
-   Apply file size, duration, processing-time, and resource limits.
-   Run FFmpeg and other media tools with restricted privileges and safe
    argument handling.
-   Keep originals separate from derived files.
-   Clean temporary files.
-   Never log raw audio, full lyrics, access tokens, provider keys,
    signed URLs, or sensitive storage paths by default.
-   Keep third-party AI processing transparent and send only relevant,
    permissioned data.
-   Processing permission is not model-training permission.
-   Provide or document data export, deletion, and retention behavior.
-   Audit approvals and consequential external actions when those
    modules are implemented.

------------------------------------------------------------------------

## 12. Later-phase endpoint inventory

These endpoints are planning placeholders. Implement them only in an
approved phase and only after schemas, authorization, provider
capabilities, and tests are specified.

### Workflows and reports

-   `POST /api/v1/workflows/music-marketing-plans`
-   `GET /api/v1/workflows/{workflow_id}`
-   `GET /api/v1/workflows/{workflow_id}/report`
-   `POST /api/v1/reports/{report_id}/feedback`

### Release and content planning

-   `POST /api/v1/release-plans`
-   `GET /api/v1/release-plans/{plan_id}`
-   `PATCH /api/v1/release-plans/{plan_id}`
-   `POST /api/v1/release-plans/{plan_id}/approve`
-   `POST /api/v1/content-plans`
-   `GET /api/v1/content-plans/{plan_id}`
-   `POST /api/v1/content-assets`
-   `GET /api/v1/content-assets/{asset_id}`

### Video generation (later phase; planning inventory only)

-   `POST /api/v1/songs/{song_id}/video-projects` --- create a
    visualizer or full-music-video project with validated input asset
    references and a typed creative brief.
-   `GET /api/v1/video-projects/{project_id}` --- retrieve project
    settings and current state.
-   `PATCH /api/v1/video-projects/{project_id}` --- update a draft
    project before rendering.
-   `POST /api/v1/video-projects/{project_id}/renders` --- enqueue an
    idempotent asynchronous render job; return `202 Accepted`.
-   `GET /api/v1/video-renders/{render_id}` --- retrieve render status,
    progress, failure code, and validation summary.
-   `GET /api/v1/video-renders/{render_id}/output` --- authorize access
    to the completed private MP4 through the configured asset-delivery
    layer.

The only initial video formats are `music_visualizer` and
`full_music_video`. The output is a completed MP4; a timeline editor is
not required. Lyric videos and standalone promotional Reels/Shorts are
out of scope unless separately approved. Requests must validate asset
ownership, rights/consent declarations, output profile, and available
renderer capabilities. Rendering must use background jobs, preserve
original assets, record provenance, and validate output integrity,
duration, resolution/aspect ratio, codec, audio presence, and sync.
Represent unavailable optional generative models as unavailable rather
than failing the baseline renderer. These routes are planned only and
must not be represented as implemented until built and tested.

### Campaigns

-   `POST /api/v1/campaigns`
-   `GET /api/v1/campaigns/{campaign_id}`
-   `POST /api/v1/campaigns/{campaign_id}/approve`
-   `POST /api/v1/campaigns/{campaign_id}/execute`
-   `POST /api/v1/campaigns/{campaign_id}/pause`
-   `GET /api/v1/campaigns/{campaign_id}/status`

Campaign execution must require scoped human approval, budget ceilings,
audit records, idempotency, and pause/stop controls. A draft or approved
plan is not evidence that execution occurred.

### Analytics

-   `POST /api/v1/integrations/{connection_id}/sync-jobs`
-   `GET /api/v1/analytics/songs/{song_id}`
-   `GET /api/v1/analytics/campaigns/{campaign_id}`
-   `GET /api/v1/analytics/reports/{report_id}`
-   `POST /api/v1/analytics/feedback`

Metrics must preserve provider name, source metric name/definition,
unit, reporting window, timezone, retrieval time, and relevant
exposure/spend context.

### Integrations

-   `GET /api/v1/integrations`
-   `POST /api/v1/integrations/{provider}/connect`
-   `GET /api/v1/integrations/{provider}/callback`
-   `DELETE /api/v1/integrations/{connection_id}`
-   `GET /api/v1/integrations/{connection_id}/capabilities`
-   `POST /api/v1/webhooks/{provider}`

Initial social publishing targets are **YouTube, Instagram, and Facebook
only**. Do not add TikTok or other social providers without a new owner
decision. Before enabling a selected provider, verify current official
documentation, permissions/scopes, app-review requirements, account and
region limitations, media requirements, commercial terms, and actual
test results. Webhooks require signature verification, replay
protection, and idempotent processing. Never assume all selected
platforms permit every publishing action or expose private analytics.
Keep draft/export available where direct publishing is unavailable.

### Consent, rights, and privacy

-   `GET /api/v1/consents`
-   `POST /api/v1/consents`
-   `POST /api/v1/consents/{consent_id}/withdraw`
-   `POST /api/v1/rights/declarations`
-   `POST /api/v1/privacy/data-export-requests`
-   `POST /api/v1/privacy/deletion-requests`

These need carefully defined scopes, auditability, retention behavior,
and authorization before implementation.

### Audit

-   `GET /api/v1/audit-events` (restricted role only)

------------------------------------------------------------------------

## 13. OpenAPI and contract testing requirements

For each implemented endpoint, document: - purpose and phase; - HTTP
method/path; - authentication and authorization; - request schema and
field validation; - success response and status code; - error
codes/statuses; - idempotency and retry behavior; - asynchronous job
behavior if relevant; - privacy/retention considerations; - tests
proving the contract.

Required tests for the first milestone: - authentication and cross-user
authorization; - song create/read/update validation; - upload intent
ownership and expiry behavior; - completion for missing, corrupt,
unsupported, and oversize files; - checksum and asset readiness; -
analysis request with ready versus unready assets; - duplicate analysis
request/idempotency; - valid and invalid job state transitions; - schema
validation and unavailable feature representation; - mock AI report
generation without credentials; - provider timeout/malformed-output
handling; - report ownership and correct analysis-version linkage; -
safe error envelopes and absence of secret leakage.

OpenAPI should be generated from the implemented routes and checked in
CI for unexpected changes if practical. Do not claim endpoints are
implemented because they are listed in this document.

------------------------------------------------------------------------

## 14. Definition of done for the first API milestone

The API milestone is complete only when:

-   [ ] The authorized user can create and retrieve a song.
-   [ ] The user can upload private audio through the configured storage
    adapter.
-   [ ] Server-side validation and checksum verification work.
-   [ ] The user can request analysis and receive a job/status resource.
-   [ ] The job state can be polled with authorization enforced.
-   [ ] FFmpeg creates a derived processing copy without overwriting the
    original.
-   [ ] Essentia/Librosa output documented features.
-   [ ] Versioned Song Intelligence is persisted with provenance and
    explicit unavailable/estimated states.
-   [ ] The mock AI provider generates a schema-valid A&R report
    offline.
-   [ ] OpenRouter can be enabled by configuration and fails safely.
-   [ ] The report can be retrieved by the authorized user.
-   [ ] API contract, authorization, media-validation, job-failure, and
    schema tests pass.
-   [ ] OpenAPI and local setup documentation match the implementation.
-   [ ] All unimplemented endpoints and unverified provider capabilities
    are clearly labeled.
-   [ ] The owner reviews the evidence and explicitly approves the next
    phase.

------------------------------------------------------------------------

## 15. Final constraints

This API specification is a proposed contract. It does not assert that
any external provider has granted access, that pretrained model licenses
permit commercial use, or that the software has been implemented or
deployed.

Do not: - deploy to production without separate authorization; - run
destructive production migrations; - connect real provider accounts
without authorization; - publish or distribute content without explicit
approval; - spend advertising money without an approved budget and
execution scope; - use uploaded music for model training without
appropriate rights and consent; - claim universal distribution/social
publishing; - fabricate metrics, analysis outputs, or successful
provider states.

**Recommended implementation order:** follow the 15 modular prompts,
align the first-slice routes with this document, and expand the API only
when the relevant phase is approved.

------------------------------------------------------------------------

## Approved scope clarification --- video outputs and social platforms

This addendum records the owner's latest decision while preserving the
first API milestone and all existing API conventions.

### Locked video formats

-   `music_visualizer`: song + artwork/metadata → audio-reactive
    graphics, motion and titles → complete validated MP4.
-   `full_music_video`: approved scene plan + permitted visual assets
    and optional locally generated scenes → assembled complete MP4.

No artist-side video editor is required. Lyric videos and standalone
promotional Reels/Shorts are deferred. The renderer must be
asynchronous, idempotent where appropriate, authorization-protected, and
validate the output. Paid generation services are not a baseline
dependency.

### Locked initial social publishing targets

-   YouTube
-   Instagram
-   Facebook

These targets do not imply that every account has permission to publish
through the API. Capabilities must be verified for the exact provider,
account type, OAuth scopes, review state, media specifications, and
quota. User approval is required before public publishing. No TikTok or
additional platform is in scope without a new owner decision.

### Scope and implementation status

All video-project/render routes above are later-phase planning entries.
The first milestone remains song upload, audio analysis, Song
Intelligence, and A&R report. API route listings are not evidence that
an endpoint has been implemented.
