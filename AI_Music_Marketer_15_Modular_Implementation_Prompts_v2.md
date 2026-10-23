# AI Music Marketer --- 15 Modular Implementation Prompts

**Version:** 1.0\
**Purpose:** A staged prompt pack for a coding agent or developer
implementing AI Music Marketer.\
**Companion document:** `AI_Music_Marketer_Complete_Specification.md`\
**Status:** Prepared for review. These prompts do not authorize
deployment, paid usage, public publishing, or external account
connections.

------------------------------------------------------------------------

## How to use this file

1.  Give the coding agent the complete specification and this prompt
    pack.
2.  Use the prompts **in order**. Do not start all 15 modules
    simultaneously.
3.  Before each prompt, make sure the previous module's acceptance
    criteria passed.
4.  Require the agent to inspect the actual repository and any existing
    phase documentation before proposing changes.
5.  Have the agent report its plan and files expected to change before
    implementation. Approve material changes before work continues.
6.  Keep API contracts aligned with the separate API specification when
    that document is prepared.
7.  Do not provide production secrets in prompts or source code.

## Global instructions --- apply to all 15 prompts

Copy these rules into every coding-agent session, even if the agent has
already seen them.

> You are implementing **AI Music Marketer**, a real product intended
> for independent artists, not a student demo. Treat
> `AI_Music_Marketer_Complete_Specification.md` as the product and
> architecture source of truth, along with any subsequently approved API
> specification and existing repository conventions.
>
> **First inspect; do not assume.** Inspect the repository, README,
> project instructions, current branch/status where available, phase
> documents, existing tests, configuration, and implemented modules.
> Report what exists and how it compares with the relevant specification
> before changing files. Reuse existing work where appropriate. Never
> rewrite the repository from scratch merely to match your preferred
> structure.
>
> The owner-selected direction is: **modular monolith with background
> workers; five specialist agents plus one orchestrator; OpenRouter
> behind an internal provider abstraction; draft-first external actions
> with explicit approval; first milestone is the complete
> song-upload-to-A&R-report vertical slice.**
>
> Proposed defaults to use unless repository inspection reveals a
> concrete compatibility issue: Next.js/React/TypeScript/Tailwind
> frontend; Python/FastAPI backend; PostgreSQL with SQLAlchemy/Alembic;
> Redis/Celery or a suitable existing queue; private object storage with
> a local development adapter; FFmpeg + Essentia + Librosa for initial
> audio analysis; OpenRouter through a replaceable provider interface;
> Docker Compose where useful; pytest and
> frontend/API/integration/end-to-end tests. Explain any proposed
> deviation and request approval before making a material architecture
> change.
>
> Work only on the module and scope named in the current prompt. Do not
> silently implement later roadmap phases. Keep interfaces typed and
> versioned, validate external and AI outputs, use consistent error
> responses, add authorization at private-resource boundaries, document
> configuration, and add tests alongside implementation. Long-running
> work should be asynchronous and expose job state. Side-effecting
> operations must be idempotent where applicable.
>
> Preserve these product safeguards: subscription tier must not secretly
> affect artistic merit or organic-opportunity scoring; paid promotion
> is separate and requires explicit budget approval; uploaded music must
> not be used for model training without the necessary rights and
> consent; observed, measured, predicted, interpreted, recommended,
> executed, and unknown information must remain distinguishable;
> unreleased media is private by default; no unsupported promise of
> distribution or universal social publishing; no invented metrics,
> lyrics, model confidence, or audience facts.
>
> **Do not** deploy to production, perform destructive production
> migrations, connect real external accounts, publish or distribute
> content, spend money, enable paid API usage, commit secrets, or
> execute consequential external actions without separate explicit
> authorization. Do not claim an integration works unless it has been
> tested or its unverified status is clearly documented.
>
> Before coding, return: (1) repository findings, (2) gaps relevant to
> this prompt, (3) a bounded implementation plan, (4) proposed files to
> add/change, (5) migration and external-service implications, and (6)
> risks/questions requiring owner approval. If a material decision is
> unresolved, stop and ask rather than inventing an answer.
>
> After coding, return: (1) summary, (2) files changed, (3) migrations,
> (4) commands/tests run and exact results, (5) acceptance criteria
> met/not met, (6) limitations, (7) configuration needed, and (8)
> recommended next prompt. Never mark a failing or unrun check as
> passed.

------------------------------------------------------------------------

# Prompt 01 --- Repository assessment and implementation plan

## Objective

Understand the existing project and produce a safe, evidence-based plan
without making implementation changes.

## Scope

-   Inspect the repository, project instructions, phase documentation,
    dependency manifests, environment examples, tests, CI, and current
    architecture.
-   Map existing files and modules against the complete specification.
-   Identify implemented, partial, missing, duplicated, and conflicting
    areas.
-   Identify any existing code that should be preserved.
-   Propose the smallest practical path to the first vertical slice.

## Required deliverables

1.  Repository inventory and architecture summary.
2.  Specification-to-repository gap matrix.
3.  Proposed module boundaries and dependency direction.
4.  Ordered milestone plan and likely files affected.
5.  Risks, security concerns, technical debt, and unresolved decisions.
6.  A clear statement of what was **not** changed.

## Acceptance criteria

-   No files changed.
-   Findings reference actual repository files and commands/results
    where available.
-   Existing work is not described as missing without checking.
-   Proposed plan starts with the song-upload-to-A&R-report vertical
    slice.
-   Any major deviation from the specification is called out for
    approval.

## Out of scope

Installing packages, editing code, migrating data, connecting services,
or deploying.

------------------------------------------------------------------------

# Prompt 02 --- Application foundation and developer experience

## Objective

Establish or safely align the minimal local development foundation after
Prompt 01's plan is approved.

## Scope

-   Create or adapt the frontend/backend structure only where needed.
-   Add configuration loading and validated environment settings.
-   Add local development instructions and safe example environment
    files.
-   Add Docker Compose only if appropriate to the existing repository.
-   Add health/readiness endpoints and a basic application startup path.
-   Establish linting, formatting, type checking, test commands, and CI
    checks consistent with the stack.
-   Keep development credentials and data separate from production.

## Required deliverables

-   Reproducible local setup.
-   Documented environment variables with no real secrets.
-   Health/readiness behavior.
-   Baseline automated checks and CI configuration.
-   Updated setup documentation.

## Acceptance criteria

-   A new developer can follow the README to run the approved local
    setup.
-   Health and readiness have documented meanings.
-   Missing/invalid required configuration fails safely with a useful
    message.
-   CI runs the agreed baseline checks.
-   No production deployment or real external account connection occurs.

## Out of scope

Full identity, media processing, agents, billing, production
infrastructure.

------------------------------------------------------------------------

# Prompt 03 --- Database, migrations, and persistence conventions

## Objective

Set up or align the persistence layer for the first vertical slice
without overbuilding future product tables.

## Scope

-   Use PostgreSQL as the proposed transactional source of truth unless
    an approved compatibility issue requires otherwise.
-   Configure SQLAlchemy and Alembic, or follow an existing equivalent.
-   Define common conventions for IDs, timestamps, constraints, indexes,
    transactions, and model organization.
-   Create only the tables required by the approved first slice, such as
    the minimum song, media asset, analysis/job, and report records.
-   Keep large media binaries in private object storage, not in database
    rows.
-   Document safe local migration and rollback practices.

## Required deliverables

-   Persistence setup and approved initial schema.
-   Reproducible migrations.
-   Database configuration documentation.
-   Tests for essential constraints and persistence behavior.

## Acceptance criteria

-   A fresh local database can be migrated to the current schema.
-   Models and migrations agree.
-   Foreign keys and ownership relationships are enforced where
    applicable.
-   No destructive production migration is executed.
-   Migration risks and rollback limitations are documented.

## Out of scope

All future campaign, billing, distribution, and proprietary-ML schemas
unless required by approved existing architecture.

------------------------------------------------------------------------

# Prompt 04 --- Identity, artist profile, and authorization foundation

## Objective

Ensure private songs and reports are associated with the correct user
and cannot be accessed across accounts.

## Scope

-   Inspect existing identity/authentication before selecting or
    implementing a solution.
-   Implement or adapt the minimum approved authentication and
    artist-profile flow.
-   Define ownership/authorization checks for private song, asset,
    analysis, job, and report resources.
-   Centralize authorization patterns instead of duplicating
    inconsistent checks.
-   Provide safe test identities/fixtures for automated tests.
-   Document session/token handling and security assumptions.

## Required deliverables

-   Minimal identity and artist-profile capability appropriate to the
    repository.
-   Reusable authorization helpers or policies.
-   Tests for authorized access, unauthorized access, and cross-user
    access.
-   Configuration and security documentation.

## Acceptance criteria

-   Private resources require authentication and ownership/role
    authorization.
-   One user cannot access another user's song, media, job, or report by
    guessing an ID.
-   Authentication failures do not reveal private resource details.
-   Test credentials are local-only and no secrets are committed.

## Out of scope

Social login providers, billing entitlements, organization/team
management, production identity-provider setup unless already approved.

------------------------------------------------------------------------

# Prompt 05 --- Song catalog and private media upload

## Objective

Allow an authorized artist to create a song record and privately upload
an audio asset safely.

## Scope

-   Implement the minimal song metadata model and create/read/update
    operations required by the vertical slice.
-   Implement private media storage behind an adapter, including a local
    development adapter.
-   Validate file size, supported formats, actual decodability, and
    relevant duration limits.
-   Do not trust filename extensions or client-provided MIME type alone.
-   Calculate a content checksum and persist asset metadata.
-   Use short-lived signed upload/download URLs where appropriate.
-   Keep originals private and separate from derived processing files.
-   Add safe temporary-file handling and resource limits.

## Required deliverables

-   Song and media-asset operations.
-   Upload flow and validation.
-   Storage abstraction and local setup.
-   User-facing validation errors.
-   Tests for valid files, unsupported formats, corrupt files, oversize
    files, authorization, and checksum behavior.

## Acceptance criteria

-   An authorized user can create a song and upload an accepted audio
    file.
-   The original asset remains private.
-   Invalid/corrupt files are rejected safely and predictably.
-   Checksum and metadata are persisted.
-   A different user cannot retrieve the asset.
-   Upload handling does not expose secrets or unrestricted storage
    paths.

## Out of scope

Public media links, video generation, distribution upload, automatic
transcription, model training.

------------------------------------------------------------------------

# Prompt 06 --- Background jobs and job lifecycle

## Objective

Run analysis asynchronously with clear, durable status and safe retry
behavior.

## Scope

-   Use Redis + Celery or the repository's suitable existing worker
    system, subject to Prompt 01 findings.
-   Define a common job lifecycle such as `queued`, `running`,
    `succeeded`, `failed`, and `cancelled`, with optional retry/approval
    states where justified.
-   Persist durable job state in PostgreSQL; do not rely on Redis as the
    sole source of important business state.
-   Record owner, task type, input version, attempt count, timestamps,
    stage, and safe error code.
-   Implement bounded retries, timeouts, idempotency where applicable,
    and safe cancellation behavior.
-   Expose authorized job-status retrieval.
-   Provide a deterministic local test mode.

## Required deliverables

-   Worker and queue configuration.
-   Job model and state-transition rules.
-   Job status API.
-   Worker error and retry policy.
-   Tests for transitions, duplicate submissions, failure, retry limits,
    and authorization.

## Acceptance criteria

-   Analysis requests return promptly and can be tracked asynchronously.
-   State transitions are valid and persisted.
-   Repeated submission does not create duplicate analysis side effects
    where idempotency is required.
-   Errors do not leak secrets or raw private media.
-   Worker failure is observable and recoverable within the documented
    policy.

## Out of scope

Distributed microservices, Kubernetes, unbounded automatic retries,
production queue operations.

------------------------------------------------------------------------

# Prompt 07 --- Audio processing and feature extraction

## Objective

Build the deterministic/pretrained audio-analysis pipeline for the first
version of Song Intelligence.

## Scope

-   Use FFmpeg to decode and create a derived processing copy without
    overwriting the original.
-   Use Essentia and Librosa for a documented initial feature set,
    subject to package/platform compatibility and license review.
-   Select a small set of useful, explainable features rather than
    computing everything by default.
-   Potential features include duration, sample rate, channels,
    loudness/energy summaries, tempo estimate, beat positions, key/mode
    estimate, spectral descriptors, MFCC/chroma, and onset/timbre
    descriptors where supported.
-   Record units, analyzer/library versions, configuration, input
    checksum, timestamps, and status.
-   Distinguish measured/derived values from estimates and
    unsupported/unavailable features.
-   Put time/resource limits around media processing and handle
    malformed inputs.

## Required deliverables

-   Processing pipeline with documented stages.
-   Typed feature schema and provenance.
-   Example outputs for rights-cleared or synthetic/test fixtures.
-   Tests for normal, silent, short, malformed, and unsupported audio
    cases as appropriate.
-   Documentation of feature meaning and limitations.

## Acceptance criteria

-   A valid upload can be processed by a background job.
-   The original file is preserved.
-   Feature outputs conform to a versioned schema.
-   Failures are represented explicitly; unavailable values are not
    fabricated.
-   The same documented configuration yields reproducible behavior
    within reasonable library/runtime tolerances.
-   No pretrained model is added before commercial license,
    requirements, cost, and quality are reviewed.

## Out of scope

Training a proprietary audio model, claims of objective universal song
quality, guaranteed hook performance.

------------------------------------------------------------------------

# Prompt 08 --- Canonical Song Intelligence and A&R report

## Objective

Persist versioned Song Intelligence and generate a useful,
evidence-linked A&R report.

## Scope

-   Define the canonical Song Intelligence schema and versioning rules.
-   Store audio features, candidate sections/hooks when available,
    optional supplied-lyrics analysis, predictions, limitations, and
    provenance.
-   Distinguish `observed`, `measured/derived`, `predicted`,
    `interpreted`, `recommended`, `executed`, and `unknown` information.
-   Re-analysis creates a new version rather than silently overwriting
    history.
-   Implement report generation through an internal AI-provider
    interface.
-   Provide a deterministic mock provider that works offline and without
    external credentials.
-   Validate AI output against a strict schema before persistence or
    display.
-   Require report claims to be grounded in supplied data; no invented
    lyrics, measurements, or confidence scores.

## Required deliverables

-   Versioned Song Intelligence model/schema.
-   Report schema and generation service.
-   Mock provider and test fixtures.
-   Report persistence and retrieval.
-   Tests for schema validation, missing data, provenance, versioning,
    and invalid model output.

## Acceptance criteria

-   A valid analysis produces a persisted, versioned intelligence
    record.
-   The mock provider generates a schema-valid A&R report offline.
-   The report distinguishes evidence, interpretation, prediction,
    recommendation, and uncertainty.
-   Missing inputs remain unavailable rather than being invented.
-   The user can retrieve the correct report for the correct analysis
    version.

## Out of scope

Audience, content, and marketing agents; training proprietary models;
unsupported commercial predictions.

------------------------------------------------------------------------

# Prompt 09 --- OpenRouter adapter and AI-provider abstraction

## Objective

Connect the report-generation layer to OpenRouter without coupling
domain logic to a single provider.

## Scope

-   Define or complete an internal provider interface.
-   Implement the OpenRouter adapter through server-side configuration.
-   Keep API keys out of frontend bundles, repository files, prompts,
    and logs.
-   Support configurable model identifier, timeouts, bounded retries,
    rate-limit/error handling, safe redaction, and usage/latency
    logging.
-   Validate structured outputs and fail safely when the provider
    returns malformed content.
-   Preserve the offline mock provider as the default for tests.
-   Send only compact, relevant, permissioned structured context; do not
    send raw audio/video to a text model when structured features
    suffice.
-   Document third-party processing implications and required
    configuration.

## Required deliverables

-   Provider interface and OpenRouter adapter.
-   Configuration example with placeholder values only.
-   Provider error mapping and usage telemetry.
-   Mocked adapter tests and optional explicitly authorized smoke-test
    instructions.

## Acceptance criteria

-   Automated tests run without network access or credentials.
-   OpenRouter can be enabled through configuration.
-   Timeouts, provider errors, malformed outputs, and rate limits are
    handled safely.
-   No secret is logged or returned to the client.
-   Provider-specific details do not leak into domain modules.
-   Any live API test is clearly distinguished from mocked tests and
    requires separate authorization.

## Out of scope

Unapproved paid calls, provider fallback chains not reviewed for
quality/privacy, autonomous external actions.

------------------------------------------------------------------------

# Prompt 10 --- Song upload-to-report user experience

## Objective

Deliver the first end-to-end artist experience from song creation
through viewing the A&R report.

## Scope

-   Build or adapt the UI to create a song, upload audio, show
    validation feedback, start analysis, and display job status.
-   Show progress by stage without implying unsupported precision.
-   Display report sections for strengths, weaknesses, possible
    improvements, evidence, predictions/interpretations, limitations,
    and unavailable data as applicable.
-   Display relevant audio measurements with units and labels.
-   Handle queued, processing, failed, cancelled, and completed states.
-   Make retry/reprocess actions explicit and safe.
-   Ensure responsive and accessible interactions.
-   Use mock/offline mode for development and automated UI tests.

## Required deliverables

-   Song upload page/form.
-   Analysis progress/status view.
-   A&R report page.
-   Error/empty/loading states.
-   Frontend tests and documented workflow.

## Acceptance criteria

-   A test user can complete the full vertical slice without manually
    editing database records.
-   The UI shows the report associated with the correct song and
    analysis.
-   Failures have actionable, non-sensitive messages.
-   The UI does not present predictions as measured facts.
-   Core flow is tested at component and/or end-to-end level.
-   No public publishing or external account connection is required.

## Out of scope

Full dashboard, subscriptions, social integrations, all five specialist
agents.

------------------------------------------------------------------------

# Prompt 11 --- Security, rights, consent, and audit baseline

## Objective

Close the privacy and governance gaps required for handling unreleased
music responsibly.

## Scope

-   Review all first-slice data flows and permissions.
-   Ensure private media access is authorized and signed URLs expire.
-   Add or document consent/rights records required for processing and
    third-party AI processing.
-   Keep processing consent distinct from model-training consent.
-   Ensure uploaded music is not used for model training without the
    required rights and consent.
-   Add safe audit events for security-sensitive operations and
    approvals.
-   Redact secrets and sensitive data from logs.
-   Document retention, export, deletion, and temporary-file cleanup
    behavior.
-   Review upload/media processing for path traversal, resource
    exhaustion, malicious files, and unsafe subprocess use.

## Required deliverables

-   Threat/risk notes and mitigations.
-   Consent/rights model or approved scoped design.
-   Audit and logging rules.
-   Security-focused automated tests.
-   Documented data retention/export/deletion behavior or a clearly
    scoped follow-up plan.

## Acceptance criteria

-   Cross-user access tests pass.
-   Credentials and private media are not leaked in logs or error
    responses.
-   Processing and model-training consent are not conflated.
-   Rights/consent limitations are visible to implementation and product
    layers.
-   Any unresolved privacy/legal question is clearly escalated rather
    than silently assumed.

## Out of scope

Legal advice, a claim of regulatory compliance without review,
production secrets setup, full enterprise compliance certification.

------------------------------------------------------------------------

# Prompt 12 --- API contract hardening and integration boundaries

## Objective

Ensure implemented endpoints have stable contracts and future
integrations cannot bypass the platform's safety rules.

## Scope

-   Align implemented endpoints with the approved separate API
    specification when available.
-   Generate OpenAPI from actual FastAPI routes.
-   Standardize authentication, authorization, request validation, error
    envelope, request IDs, pagination, timestamps, and idempotency
    behavior.
-   Use `202 Accepted` and status resources for long-running jobs where
    appropriate.
-   Define provider capability interfaces and a capability registry
    shape without claiming unverified provider support.
-   Add signature verification and replay protection only for webhook
    endpoints that are actually in scope.
-   Clearly label integrations as mock, configured, tested, or
    unverified.

## Required deliverables

-   Updated OpenAPI docs.
-   Endpoint contract tests.
-   Stable error-code documentation.
-   Provider interface/capability documentation.
-   Integration status matrix.

## Acceptance criteria

-   Every implemented endpoint has a schema, authorization rule, error
    contract, and tests.
-   Generated OpenAPI matches actual route behavior.
-   Retries and idempotency behavior are documented and tested where
    required.
-   No integration is represented as production-ready without
    verification.
-   No universal distribution/social publishing promise is made.

## Out of scope

Implementing all external providers, connecting real artist accounts,
payments, public webhooks not required by the first slice.

------------------------------------------------------------------------

# Prompt 13 --- Agent framework and orchestrator skeleton

## Objective

Establish bounded, typed agent contracts and orchestration foundations
only after the first vertical slice is reliable.

## Scope

-   Define common agent input/output contracts, versioning, run status,
    provenance, and safe error representation.
-   Define orchestrator responsibilities: task classification,
    prerequisite/permission checks, agent selection, bounded retries,
    schema validation, conflict handling, output assembly, and audit
    metadata.
-   Add the five specialist interfaces: Music Analysis, Audience
    Intelligence, Content Strategy, Marketing Strategy, Analytics &
    Optimization.
-   Initially wire only the Music Analysis/report capability needed by
    the existing vertical slice; keep future specialist implementations
    as explicitly unimplemented stubs/interfaces where appropriate.
-   Add timeout, token/cost budget, allowlisted tool, and maximum
    workflow-depth controls.
-   Prevent unbounded agent-to-agent loops.
-   Do not expose private chain-of-thought; provide concise rationale
    and evidence references.

## Required deliverables

-   Agent contract definitions.
-   Orchestrator skeleton.
-   Run metadata and schema validation.
-   Mock agent fixtures.
-   Tests for invalid output, timeouts, bounded retries, and permission
    checks.

## Acceptance criteria

-   All five specialist roles and one orchestrator are represented by
    explicit interfaces/contracts.
-   The first-slice Music Analysis/report path still works.
-   Future agents are not falsely represented as functional when only
    stubs exist.
-   Agent runs record schema/model/prompt versions and status where
    applicable.
-   Workflow limits and failure handling are tested.

## Out of scope

Fully implementing all agents, autonomous campaign execution,
unrestricted tool use, multi-agent loops.

------------------------------------------------------------------------

# Prompt 14 --- CI, regression, observability, and first-slice release gate

## Objective

Prove the first vertical slice is reliable enough for owner review in a
controlled non-production environment.

## Scope

-   Run and strengthen unit, API-contract, integration, authorization,
    media-validation, job-lifecycle, provider-adapter, and end-to-end
    tests.
-   Use licensed/rights-cleared fixtures or generated test signals;
    document fixture provenance.
-   Add structured logs and useful metrics for job duration/failure,
    analysis stages, provider latency/errors, and safe usage/cost
    accounting.
-   Ensure logs omit secrets, raw audio, and full lyrics by default.
-   Add CI gates for lint, type checks, tests, and migration
    consistency.
-   Document backup/recovery considerations appropriate to the current
    environment.
-   Record unresolved performance, cost, licensing, security, and UX
    issues.

## Required deliverables

-   CI quality gates.
-   Test report with actual commands/results.
-   Observability and troubleshooting notes.
-   First-slice acceptance report.
-   Open issues and risk register.

## Acceptance criteria

-   Required CI checks pass, or failures are explicitly reported with
    owners/next steps.
-   The end-to-end upload-to-report workflow is repeatable in the
    documented environment.
-   Core failure cases are tested.
-   No secrets are committed.
-   Migration state is reviewed.
-   The owner can inspect evidence for each acceptance criterion.

## Out of scope

Production launch, scaling claims unsupported by load tests, production
incident-response certification.

------------------------------------------------------------------------

# Prompt 15 --- Handoff, documentation, and next-phase proposal

## Objective

Prepare a clean handoff for the owner and friend, and propose the next
approved increment without implementing it automatically.

## Scope

-   Review the implementation against the complete specification and
    first-slice acceptance checklist.
-   Update README and developer docs for setup, architecture, data flow,
    tests, configuration, known limitations, and troubleshooting.
-   Document which features are real, mocked, unimplemented, or
    unverified.
-   List migrations and how they are applied safely in development.
-   Summarize privacy/rights assumptions and any unresolved questions.
-   Propose the next phase based on evidence, likely Audience
    Intelligence or further Song Intelligence quality, but do not start
    it without approval.
-   Prepare a reproducible handoff report.

## Required deliverables

1.  Final first-slice status: passed, partially passed, or blocked.
2.  Checklist with evidence for each item.
3.  Files/modules changed and important design decisions.
4.  Test commands and exact outcomes.
5.  Configuration required, using placeholders only.
6.  Known limitations and unresolved risks.
7.  Recommended next prompt and rationale.
8.  Explicit confirmation that no deployment or external side effect was
    performed.

## Acceptance criteria

-   The owner can reproduce the workflow from documentation.
-   The report distinguishes verified functionality from mocks and
    assumptions.
-   Every failed/unrun acceptance item is visible.
-   No future phase is silently started.
-   No deployment, public publishing, advertising spend, or real
    external account connection occurred.

## Out of scope

Automatic deployment, production migration, launching paid campaigns,
claiming full platform completion.

------------------------------------------------------------------------

## Milestone gate: song-upload-to-A&R-report

Do not move beyond the first vertical slice until the owner reviews
evidence for all of the following:

-   [ ] Authorized user can create a song record and privately upload
    audio.
-   [ ] Validation, checksum, storage, and job state transitions work.
-   [ ] FFmpeg creates a derived processing copy without overwriting the
    original.
-   [ ] Essentia/Librosa produce a documented initial feature set.
-   [ ] Versioned Song Intelligence stores units, provenance, and
    uncertainty/unavailable statuses.
-   [ ] Mock AI provider generates a schema-valid report without
    external credentials.
-   [ ] OpenRouter adapter is configurable and handles failures safely.
-   [ ] UI displays measurements, report, predictions, and limitations.
-   [ ] Authorization, invalid/corrupt files, job failures, schema
    validation, and API contracts are tested.
-   [ ] Documentation, migration review, and CI checks pass.
-   [ ] Owner explicitly approves moving to the next phase.

## Final operating rule

**These prompts are implementation instructions, not permission to
execute consequential actions.** Architecture changes, destructive
migrations, paid API usage, external account connections, production
deployment, public publishing, distribution submissions, and advertising
spend each require separate explicit authorization.

------------------------------------------------------------------------

## Approved scope clarification --- future video and publishing phases

The existing 15 prompts remain the ordered first implementation pack. Do
not broaden the first song-upload-to-A&R-report milestone. Once the
owner approves the relevant later phase, add implementation prompts for
the following work in order:

### Future phase A --- video-rendering foundation

-   Inspect existing media/storage/job modules before changes.
-   Define typed, versioned contracts for render requests, timelines,
    scene plans, render jobs, output assets, provenance, and validation.
-   Implement a deterministic FFmpeg-based renderer and graphics layer.
-   Keep uploaded originals immutable; keep output private by default.
-   Add job progress, cancellation where safe, bounded retries,
    idempotency, resource limits, cleanup policy, and observability.
-   Test malformed assets, unsupported codecs, missing fonts, failed
    renders, audio sync, aspect ratio, output integrity, and
    authorization.

### Future phase B --- music visualizer

-   Accept song, artwork, metadata, and selected visualizer style.
-   Derive audio-reactive data with documented methods; do not ask an
    LLM to invent measured audio values.
-   Render a complete synchronized MP4 with titles and transitions.
-   Validate the output and expose download access only to the
    authorized owner.

### Future phase C --- full music video

-   Generate a structured scene plan from approved song context and
    brief.
-   Compose visuals from artist assets, rights-cleared assets,
    deterministic graphics, and optional local generative models behind
    adapters.
-   Benchmark candidate models on the actual RTX 4060 8 GB VRAM system;
    check model licenses for commercial use and record limitations.
-   Assemble scenes to a complete song-length video and render a final
    MP4.
-   Clearly distinguish generated, supplied, licensed, and templated
    visuals.
-   Do not require paid generation APIs for the baseline or promise
    cinematic quality before a measured benchmark supports it.

### Future phase D --- selected social integrations

Initial targets only: **YouTube, Instagram, Facebook**. For each, verify
current official documentation, account eligibility, OAuth scopes,
review requirements, media specifications, quotas, and actual end-to-end
test results before enabling capabilities. Support draft/export if
direct publishing is unavailable. Publishing remains approval-gated. No
TikTok or additional social provider without a new owner decision.

These future prompts do not authorize paid API use, account connection,
public publishing, production deployment, or advertising spend.
