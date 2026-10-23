# Architecture Index

## Implementation Guide

**This index is not the full contract. Do not implement from this file alone; follow the artifact paths below.**

All paths are relative to this artifact root.

### Global artifacts

- `unit_graph.yaml` — all implementers: locate the assigned unit, source anchors, caller contracts, dependencies, and shared references. Source anchors are evidence, not rewrite scope.
- `migration_boundary.yaml` — all implementers: `must_rewrite` defines the requested rewrite scope; preserve `copy_as_is`, `legacy_allowed_to_remain`, and deferred cleanup constraints. Existing SQLite data must remain intact.
- `wire_contracts.yaml` — API and persistence implementers: filter rows by `unit`, or include `global`; frozen legacy routes retain methods, paths, statuses, schemas, and response shapes.
- `shared_modules.yaml` — implementers of shared code: filter by `used_by_units`; use only listed model/DTO/session names and follow the recorded split/wrap notes.
- `cross_unit_state.yaml` — implementers of async/API handoff: filter flows where writer or reader is the assigned unit; preserve paired database state and verify status polling at runtime.
- `project-structure.md`, `tech-stack.md`, `data-model.md` — project layout, dependency facts, and existing persisted data. `project-structure.md` records both the delivered target and preserved source behavior.

No `seams.yaml` was emitted: no separate frozen runtime subsystem or protocol cut point is required by the requested in-place full-stack rewrite. The old API contracts are recorded in `wire_contracts.yaml`.

## Implementation units

For every unit, read `unit_graph.yaml`, `migration_boundary.yaml`, its three unit files, and only the relevant global rows before changing code.

### Unit: `web_entry`
- External trigger: `GET /`, legacy `GET /api/health`, and versioned `GET /api/v1/health`.
- Read `units/web_entry/behavior.yaml` for response and startup behavior; `units/web_entry/bindings.yaml` for FastAPI, CORS, router registration, and configuration; `units/web_entry/unit_decomposition.yaml` for advisory splits only.
- Filter wire rows by `unit: web_entry`; shared modules by `used_by_units`; no cross-unit state is recorded.
- Before DONE report artifacts read, preserved route behavior, unresolved/deferred contracts, and tests/build/runtime evidence.

### Unit: `frontend_spa`
- External trigger: browser navigation to the Next.js frontend and interaction with private artist onboarding, dashboard, upload/report, and video-render workflows.
- Read `units/frontend_spa/behavior.yaml` for onboarding gates, owner-visible states, analysis/render job polling, consent, and download behavior; `units/frontend_spa/bindings.yaml` for API client, frontend contracts, and render controls; `units/frontend_spa/unit_decomposition.yaml` for advisory splits only.
- Filter `unit_graph.yaml` dependencies; the frontend uses the versioned song API and analysis worker job/status endpoints.
- Before DONE report artifacts read, implemented visible states, API dependencies, separate promotional consent, private download behavior, and lint/typecheck/build/browser evidence.

### Unit: `song_api`
- External trigger: legacy `/api/songs` routes and v1 private upload, verification, analysis, audience-hypothesis, release-plan, video-render, and provider-capability routes.
- Read `units/song_api/behavior.yaml` for legacy behavior, consent/rights gates, idempotency, render status, private download errors, and connection-consent revocation; `units/song_api/bindings.yaml` for legacy/v1 routes, database, private storage, renderer, and provider capability wiring; `units/song_api/unit_decomposition.yaml` for advisory splits only.
- Filter `wire_contracts.yaml` by `unit: song_api`; shared modules by `used_by_units`; cross-unit flows by writer/reader; preserve legacy integer IDs and response contracts while enforcing v1 owner scoping and idempotency.
- Before DONE report artifacts read, implemented preserved behaviors, consent/idempotency/download contracts, unresolved/deferred contracts, and contract tests.

### Unit: `platform_connections`
- External trigger: authenticated request to list/start/remove a YouTube, Instagram, or Facebook profile connection, or the provider redirect to its OAuth callback.
- Read `units/platform_connections/behavior.yaml` for owner-bound one-time OAuth state, separate platform consent, server-side token exchange/encryption, expiry, and local-vs-provider revocation; `units/platform_connections/bindings.yaml` for route, provider scope, config, and storage contracts; `units/platform_connections/unit_decomposition.yaml` for advisory splits only.
- Filter `unit_graph.yaml`, `wire_contracts.yaml`, `shared_modules.yaml`, and `cross_unit_state.yaml` by this unit; preserve read-only scopes and never add publishing permissions without a new owner decision.
- Before DONE report provider setup requirements, scope and credential handling, callback/consent tests, frontend build evidence, and limitations of unconfigured real provider apps.

### Unit: `campaign_api`
- External trigger: legacy `/api/campaigns` routes.
- Read `units/campaign_api/behavior.yaml` for CRUD/task updates; `units/campaign_api/bindings.yaml` for routes and DB dependency; `units/campaign_api/unit_decomposition.yaml` for advisory splits only.
- Filter wire contracts and shared modules by unit; include song relationship checks.
- Before DONE report legacy compatibility and test evidence.

### Unit: `artist_api`
- External trigger: legacy `/api/artist/profile` and `/api/artist/calendar`.
- Read `units/artist_api/behavior.yaml`, `units/artist_api/bindings.yaml`, and `units/artist_api/unit_decomposition.yaml`.
- Filter wire contracts and shared modules by unit.
- Before DONE report profile default/upsert behavior, calendar relationship validation, and test evidence.

### Unit: `run_api`
- External trigger: legacy `GET /api/runs/{run_id}`.
- Read `units/run_api/behavior.yaml`, `units/run_api/bindings.yaml`, and `units/run_api/unit_decomposition.yaml`.
- Filter wire contracts/shared modules by unit and cross-unit flows where it reads worker state.
- Before DONE report nested run response compatibility and test evidence.

### Unit: `stats_api`
- External trigger: legacy `GET /api/stats`.
- Read `units/stats_api/behavior.yaml`, `units/stats_api/bindings.yaml`, and `units/stats_api/unit_decomposition.yaml`.
- Filter wire contracts/shared modules by unit and include dependencies to song, campaign, and artist data.
- Before DONE report aggregation compatibility and test evidence; do not relabel simulated values as measured outcomes.

### Unit: `analysis_worker`
- External trigger: legacy pipeline task scheduled on song create/reanalysis, or a v1 asset-verification/song-analysis/video-render job.
- Read `units/analysis_worker/behavior.yaml` for state transitions, rights/consent rechecks, render progress, output validation/persistence, failure behavior, and transaction scope; `units/analysis_worker/bindings.yaml` for worker paths, private storage, FFmpeg renderer, DB, and configuration wiring; `units/analysis_worker/unit_decomposition.yaml` for advisory splits only.
- Filter wire contracts by `unit: global`, shared modules by `used_by_units`, and state flows where this unit writes or reads. Preserve old legacy run outputs for existing API readers while implementing versioned first-slice analysis separately.
- Before DONE report preserved/changed state transitions, consent enforcement, output validation/provenance, failure handling, migrations, tests, and runtime evidence.
