# AI Music Marketer

A private-first prototype for independent artists. The app includes a local artist profile/onboarding flow and dashboard, followed by a private audio upload, rights declarations, separate processing/provider consent, media validation, versioned Song Intelligence, and an evidence-limited A&R report.

The app supports explicit read-only account connections for YouTube, Instagram professional accounts, and Facebook profiles when provider credentials are configured. It does not publish music, manage Facebook Pages, run ads, or promise commercial results.

## Project layout

```text
backend/
  core/                 # local bearer auth and safe API errors
  domain/               # v1 SQLAlchemy models and Pydantic contracts
  routers/              # preserved legacy endpoints, /api/v1, and OAuth callbacks
  services/             # private storage, audio/video processing, OAuth and report providers
  workers.py            # preserved legacy pipeline
  services/job_runner.py# first-slice asynchronous job processing
frontend/
  app/                  # Next.js App Router UI
  lib/                  # v1 API client and shared contracts
tests/                  # legacy and v1 API integration tests
scripts/package_demo.ps1
```

The old `/api/*` endpoints and tables remain in place. The v1 app uses separate `v1_*` SQLite tables, including owner-scoped artist profiles, songs, rights declarations, and append-only consent events; startup creates missing tables without replacing the existing database. The dashboard lists the authenticated workspace's songs with cursor pagination. No destructive data migration is performed.

## Local setup

Requirements: Python 3.11+ (tested with Python 3.14), Node.js 22+, npm, and FFmpeg/FFprobe available on `PATH`.

1. Create local settings and a private workspace token:

   ```powershell
   Copy-Item .env.example .env
   $random = [Security.Cryptography.RandomNumberGenerator]::Create()
   $bytes = New-Object byte[] 32
   $random.GetBytes($bytes)
   $token = [Convert]::ToBase64String($bytes)
   $random.Dispose()
   (Get-Content .env) -replace '^APP_API_TOKEN=.*$', "APP_API_TOKEN=$token" | Set-Content .env -Encoding ASCII
   ```

   Keep `.env` private. The UI asks for this token and keeps it in the current browser session only.

   To enable optional read-only social account connections, finish installing the Python dependencies in step 2 first, then configure the OAuth key and provider apps.

2. Install Python and frontend dependencies:

   ```powershell
   if (-not (Test-Path .venv)) { py -m venv .venv }
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Set-Location frontend
   npm ci
   Set-Location ..
   ```

   To enable optional read-only social account connections, generate a Fernet key and set `APP_TOKEN_ENCRYPTION_KEY` in `.env`:

   ```powershell
   .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Register the exact callback URLs in each provider's developer app and set the matching client ID, client secret, and redirect URI variables from `.env.example`. YouTube needs the YouTube Data API enabled; Instagram uses Instagram Login and is limited to professional accounts. Callback URIs must match the registered URI exactly. OAuth credentials remain server-side. If the encryption key is lost or changed, existing stored tokens cannot be decrypted; disconnect them and reconnect after setting a new key.

   Provider setup references: [Google/YouTube server-side OAuth](https://developers.google.com/youtube/data/guides/auth/server-side-web-apps), [Instagram Business Login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login), and [Facebook Login permissions](https://developers.facebook.com/documentation/facebook-login/guides/permissions). On non-local deployments, use HTTPS and set `APP_FRONTEND_URL` to the browser-facing frontend origin.

3. Start the API and web app in separate PowerShell windows:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

   ```powershell
   Set-Location frontend
   npm run dev
   ```

   Open `http://localhost:3000`. API documentation is at `http://localhost:8000/docs`.

### Sharing on a local network

Both development servers bind to `0.0.0.0`. To open the app from another device, use the host computer's LAN address, for example `http://192.168.1.20:3000`. Add that exact origin to `APP_CORS_ORIGINS` in `.env` (for example `http://localhost:3000,http://192.168.1.20:3000`) and restart the API. Allow inbound TCP ports 3000 and 8000 in the host firewall only on a trusted private network. The API token is a shared local-workspace credential, not multi-user authentication; do not expose this prototype to the public internet.

The browser derives the API host from the hostname used to open the web app, so both services should use the same host name/IP. For HTTPS reverse-proxy use, set `NEXT_PUBLIC_API_BASE_URL` at frontend build time to the HTTPS API origin.

## Audio and report behavior

- Original audio is stored under `APP_MEDIA_STORAGE_PATH` outside the public frontend directory. Uploads are bounded by size and duration, checksummed, and validated by decoding through FFprobe; FFmpeg creates a derived mono WAV for analysis.
- Optional artist-supplied lyrics are analyzed locally for literal keyword themes and repeated-line candidates. The full submitted text is not retained or sent to OpenRouter; only derived observations are stored, and they are explicitly not audience-response or commercial predictions. FFmpeg can identify silence-separated neutral segment candidates, but does not label musical roles or audio hooks. Automatic transcription and pretrained predictions are not enabled.
- The v1 audience hypotheses are generated only from available song-specific evidence and artist-selected context. They include uncertainty and a manual validation experiment; that v1 feature does not infer demographics, platform affinity, or private recommendation behavior. The separate legacy agent pipeline's audience matches are generic heuristics, not verified demographics.
- Release plans use a dated or relative pre-release/release-day/post-release checklist. Draft approval is an internal review state only: the app does not connect distributors, publish, or spend money, and it makes no cost or reach estimates. The separate read-only social-profile links do not authorize any release-plan actions.
- Private video rendering supports music visualizers and full music videos as completed 1280×720 H.264/AAC MP4s. The local FFmpeg renderer creates deterministic waveform or spectrum motion graphics and title cards from the authorized original audio; it does not require new artwork uploads, generate cinematic AI footage, or publish the result. A separate promotional-media consent is required and rechecked while queued/running. Outputs remain under private media storage, are validated before download, and include render settings, source checksum, and a generated-scene plan.
- Optional social connections use provider OAuth callbacks with one-time expiring state and a separate workspace-level `platform_account_connection` consent. YouTube requests `youtube.readonly`; Instagram requests only `instagram_business_basic`; Facebook requests only the default public profile. Access/refresh tokens are encrypted in SQLite using `APP_TOKEN_ENCRYPTION_KEY`, never returned to the browser, and removed locally when disconnected or when platform-account consent is withdrawn. Provider token expiry is shown so the artist can reconnect. Removing a local token does not revoke the grant at Google/Meta; use the provider's security settings for full revocation.
- Social account linking is not publishing authorization. The app does not request YouTube upload, Instagram content-publish, Facebook Page, advertising, or write scopes; Facebook Pages are not connected. Social publishing and distribution remain disabled.
- Before upload, the artist must record separate recording/composition rights bases and grant scoped audio-processing consent. Analysis also requires separate derived-analysis-storage consent. A separate opt-in is required before sending the track title and structured measurements to OpenRouter. Without that opt-in the configured OpenRouter deployment uses the offline mock report; original audio is never sent to the AI provider. No uploaded music is used for model training.
- The dashboard shows append-only consent history and permits withdrawal of active grants. Withdrawal blocks queued work; the video renderer also rechecks promotional consent at progress checkpoints. Withdrawal does not delete stored audio, completed analysis, or already completed renders.
- From a completed analysis report, choose **Run agent pipeline** to run all five deterministic legacy agents using the saved analysis, song metadata, and only derived lyric candidates. Their latest handoffs and outputs are stored in `v1_agent_pipeline_runs` and shown in the dashboard. Running again replaces that analysis's previous pipeline result; active rights, audio-processing consent, and derived-analysis-storage consent are required.
- The agent pipeline's audience segments are generic heuristic matches, its energy/valence use genre defaults, and its analytics figures are simulated. Treat its campaign and budget suggestions as drafts, not evidence or forecasts; this pipeline does not publish, buy ads, contact platforms, or execute campaign tasks.
- FFprobe/FFmpeg file facts are measured. Librosa tempo/RMS and Essentia key are optional and explicitly labeled estimated when available. Missing tools or unsupported measurements are surfaced as unavailable; they are never fabricated.
- `APP_AI_PROVIDER=mock` is the offline default. It emits a small, deterministic report and does not call an external service.
- To use OpenRouter, set `APP_AI_PROVIDER=openrouter`, `APP_OPENROUTER_API_KEY`, and `APP_OPENROUTER_MODEL` in the backend environment. Only the song title and derived structured analysis are sent for report generation; the original audio is not sent. The response is schema-validated, evidence references are checked, and provider failures are recorded as job errors. Never put the provider key in a `NEXT_PUBLIC_*` variable.

## Phase 5–8: Ollama LLM, YouTube Publishing, and Lyric-Video Generation

### Ollama Local LLM Setup

Ollama provides a lightweight local LLM for generating YouTube metadata (titles, descriptions, tags) without external API calls.

1. **Install and run Ollama**:
   - Download Ollama from [ollama.com](https://ollama.com/)
   - Run the Ollama service (default port: 11434)
   - Optionally pull a model: `ollama pull phi` (phi is the default)

2. **Configure the app**:
   - Set `APP_OLLAMA_ENABLED=true` in `.env` (default)
   - Set `APP_OLLAMA_BASE_URL=http://localhost:11434` (default)
   - Set `APP_OLLAMA_MODEL=phi` (default)
   - Set `APP_OLLAMA_TIMEOUT_SECONDS=30` (default)

3. **Verify**:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
   # In browser: GET http://localhost:8000/api/v1/capabilities
   # Check "ollama_available": true
   ```

If Ollama is unavailable, the app gracefully falls back to template-based metadata generation. Prompt injection safety is built-in; user-supplied inputs are sanitized before being used in LLM prompts.

### YouTube Publishing Setup

To publish rendered videos directly to YouTube:

1. **Enable YouTube Data API**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the "YouTube Data API v3"

2. **Create OAuth credentials**:
   - In Google Cloud Console, go to **Credentials**
   - Click **+ Create Credentials** > **OAuth client ID**
   - Choose **Desktop application** or **Web application**
   - Add authorized redirect URI: `http://localhost:8000/api/v1/oauth/callback/youtube` (or your production URL)
   - Download the JSON file and copy the values:
     - `client_id` → `APP_YOUTUBE_OAUTH_CLIENT_ID` in `.env`
     - `client_secret` → `APP_YOUTUBE_OAUTH_CLIENT_SECRET` in `.env`
     - Redirect URI → `APP_YOUTUBE_OAUTH_REDIRECT_URI` in `.env`

3. **Configure encryption key** (if not already set):
   ```powershell
   .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Set the output as `APP_TOKEN_ENCRYPTION_KEY` in `.env`.

4. **Connect YouTube account**:
   - In the app, go to **Platform Connections** or OAuth settings
   - Click **Connect YouTube**
   - Authorize the app to access your YouTube account (read-only)
   - Your access token is encrypted and stored locally

5. **Publish workflow**:
   - Complete a video render (music visualizer or full music video)
   - Click **Publish to YouTube** or call `POST /api/v1/video/{render_id}/publish-youtube`
   - Metadata is automatically generated via Ollama
   - Video is uploaded as "unlisted" (can be shared but not listed)
   - Upon success, video URL is stored and available for sharing

**Rate limits**: 10 YouTube publish jobs per hour per account (configured in `APP_YOUTUBE_PUBLISH_RATE_LIMIT_PER_HOUR`).

**Error handling**:
- Quota exceeded (403): Job is retried by the scheduler
- Token revoked (401): User must reconnect YouTube
- Invalid video (400): Job fails permanently
- Server error (5xx): Job is retried

### Lyric-Video Rendering

Generate videos with optional lyrics overlay (SRT or LRC format).

1. **Supported formats**:
   - **SRT** (SubRip): Standard subtitle format with timecodes and text
   - **LRC** (Lyric): Lightweight lyrics format with timestamps

2. **Render modes**:
   - `waveform`: Audio waveform visualization (default)
   - `spectrum`: Frequency spectrum visualization

3. **API endpoint**:
   ```
   POST /api/v1/video/{render_id}/generate-lyric-video
   ```

   Returns a job status that can be polled via:
   ```
   GET /api/v1/jobs/{job_id}
   ```

4. **Rate limits**: 20 lyric-video render jobs per hour (configured in rate limiter).

5. **Example SRT lyrics file**:
   ```
   1
   00:00:01,000 --> 00:00:03,000
   First verse line

   2
   00:00:04,000 --> 00:00:06,000
   Second verse line
   ```

6. **Example LRC lyrics file**:
   ```
   [00:10.50]First verse line
   [00:15.00]Second verse line
   [01:05.75]Chorus line
   ```

### Publishing Workflow

Typical end-to-end workflow:

1. **Upload audio** → `POST /api/v1/uploads`
2. **Verify and analyze** → `POST /api/v1/analyses` (creates analysis job)
3. **Render video** → `POST /api/v1/videos` (creates render job, generates MP4)
4. **Generate lyric video** (optional) → `POST /api/v1/video/{render_id}/generate-lyric-video`
5. **Publish to YouTube** → `POST /api/v1/video/{render_id}/publish-youtube`
   - Metadata is generated via Ollama (or fallback templates if unavailable)
   - Video is uploaded as unlisted
   - Video URL is stored in render record under `platform_urls["youtube"]`
   - Job state transitions: queued → publishing → published (or failed on permanent error)

### Configuration Reference

New settings for Phase 5–8:

```env
# Ollama LLM
APP_OLLAMA_ENABLED=true                         # Enable Ollama integration
APP_OLLAMA_BASE_URL=http://localhost:11434      # Ollama service endpoint
APP_OLLAMA_MODEL=phi                            # Model to use for generation
APP_OLLAMA_TIMEOUT_SECONDS=30                   # Timeout for Ollama requests

# YouTube
APP_YOUTUBE_UPLOAD_MAX_SIZE_BYTES=134217728     # 128 MB max video size
APP_YOUTUBE_PUBLISH_RATE_LIMIT_PER_HOUR=10      # Rate limit for publishing

# Lyric video
APP_LYRIC_VIDEO_MAX_RENDER_TIME_SECONDS=300     # Max rendering time (5 min)
APP_LYRIC_VIDEO_SUBTITLE_FORMAT=srt             # Default subtitle format

# OAuth credentials (see YouTube setup above)
APP_YOUTUBE_OAUTH_CLIENT_ID=...
APP_YOUTUBE_OAUTH_CLIENT_SECRET=...
APP_YOUTUBE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/oauth/callback/youtube
```

### Testing

All new functionality is covered by comprehensive tests:

```powershell
# Test Ollama provider (metadata generation, fallback, injection safety)
.\.venv\Scripts\python.exe -m pytest tests/test_ollama_provider.py -v

# Test YouTube publisher (upload, error classification, rate limiting)
.\.venv\Scripts\python.exe -m pytest tests/test_youtube_publisher.py -v

# Test lyric video generation (SRT/LRC parsing, ASS subtitle generation)
.\.venv\Scripts\python.exe -m pytest tests/test_lyric_video_generation.py -v

# Test job runner (job state transitions, error recovery)
.\.venv\Scripts\python.exe -m pytest tests/test_job_runner_publishing.py -v

# End-to-end publishing workflow
.\.venv\Scripts\python.exe -m pytest tests/test_e2e_publishing_workflow.py -v

# Run all tests with coverage
.\.venv\Scripts\python.exe -m pytest tests/ -v --cov=backend --cov-report=term
```

**Test coverage**: All new services (ollama_provider, youtube_publisher, lyric_video_generator) and job runner extensions are tested with mocked external dependencies. Tests skip gracefully if FFmpeg is unavailable.

### Notes on Design

- **Fallback behavior**: If Ollama is unavailable, metadata generation falls back to template-based output. The app never fails due to Ollama being offline.
- **Error classification**: YouTube errors are classified as recoverable (retry) or permanent (fail). Only recoverable errors trigger job retry; permanent errors fail immediately.
- **Encryption**: OAuth access tokens are encrypted at rest using the configured `APP_TOKEN_ENCRYPTION_KEY`. Tokens are never exposed to the browser.
- **Rate limiting**: New endpoints are rate-limited (20/hour for lyric video, 10/hour for YouTube) using slowapi decorators.
- **Audit logging**: All publishing events are logged with structured information (no sensitive data) for debugging and monitoring.

- Semantic verse/chorus and audio hook detection, pretrained predictions, evidence-grounded audience predictions, AI-generated cinematic video, and real campaign metrics are not enabled. The separate legacy agent pipeline exposes generic audience heuristics and simulated metrics only. Video rendering is limited to local motion graphics; capabilities and report limitations state unavailable features explicitly.

## Data and privacy

The default database is `music_marketer.db`; the first-slice media directory defaults to `private-media/`. Both are local and excluded from the presentation ZIP. OAuth credentials in `.env` and the token-encryption key must be backed up separately and securely; losing the key prevents stored-token decryption. Back up or securely delete local data yourself when handling real unreleased music. This prototype has one configured `APP_AUTH_USER_ID` and one bearer token; it is not a multi-tenant identity system or a production security boundary.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
Set-Location frontend
npm run typecheck
npm run lint
npm run build
```

## Testing

To run all tests with coverage:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v --cov=backend --cov-report=term
```

To run tests with coverage report (HTML):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v --cov=backend --cov-report=term-missing --cov-report=html
```

Open `htmlcov/index.html` in a browser to view detailed coverage per module.

### Coverage Baseline

**Phase 1 Coverage Baseline: 81%** (established October 22, 2026)

All tests passing: 31 passed, 4 skipped (FFmpeg/audio tests skipped on systems without dependencies).

Module highlights:
- Core models/schemas: 100%
- API v1 routers: 83%
- Job runner/services: 73% (audio/video tests conditional on dependencies)
- Authorization/consent: 100%

Track this in CI as a quality gate for future phases.

### Audio and Video Testing

Real audio and video tests require:
- **FFmpeg and FFprobe**: Installed and available on PATH. CI installs these automatically.
- **Librosa** (optional): For tempo and RMS energy extraction. Tests skip gracefully if unavailable.
- **Essentia** (optional): For musical key extraction. Tests skip gracefully if unavailable.

Tests automatically skip if dependencies are unavailable, using pytest `skipif` guards.

### Known Limitations — Phase 1

#### Background Job Auto-Execution

Jobs (song analysis, video render) are queued in the database and executed when `run_v1_job()` is called programmatically (e.g., in tests). The current implementation does not include automatic job scheduling (APScheduler, Celery, etc.); jobs remain queued until explicitly invoked.

**Status:** Documented for Phase 2. Tests manually invoke `run_v1_job()` to verify job execution; automatic scheduling is not yet implemented.

**Workaround:** Call `run_v1_job()` in your own scheduler or HTTP endpoint if deploying beyond local development.

## Create a shareable source ZIP

Run from the project root:

```powershell
.\scripts\package_demo.ps1
```

The archive is written to `dist/ai-music-marketer-demo.zip`. It excludes dependency folders, build outputs, local `.env` files, databases, and private media. The recipient installs dependencies and configures a fresh local token following this README.

## Docker Compose

Copy `.env.example` to `.env`, set a strong `APP_API_TOKEN`, then run `docker compose up --build`. The frontend is on port 3000 and the API on port 8000. Update `APP_CORS_ORIGINS` in `.env` with the exact LAN frontend origin before using it from another device. SQLite and private audio live in the persistent `app-data` volume.
