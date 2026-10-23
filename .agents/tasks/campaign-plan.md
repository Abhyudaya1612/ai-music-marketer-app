# Implementation Plan: AI-Powered Song Promotion & Marketing Campaign Planner

## Exploration Summary

**Codebase architecture:**
- Backend: FastAPI (main.py), SQLAlchemy ORM with Base in backend/database.py
- Dual model systems: legacy models in backend/models.py (Song, CampaignPlan, CampaignTask with integer PKs) and new domain models in backend/domain/models.py (StudioSong with UUID PKs, standard v1 API)
- v1 API router: backend/routers/v1.py (large file, ~1100+ lines, versioned endpoints)
- Existing campaigns router: backend/routers/campaigns.py (legacy task-planning, not the marketing campaign feature)
- Auth pattern: current_owner dependency in backend/core/auth.py returns owner_id string
- Ollama integration: backend/services/ollama_provider.py with httpx client, fallback pattern on connection error
- Frontend: Next.js 15 (app directory router), TypeScript, Tailwind CSS, lucide-react icons. No recharts currently (will add for charts).
- Database: SQLite by default (music_marketer.db)
- Testing: pytest with conftest.py fixtures, in-memory SQLite databases

**Key decision: Use legacy v1_* naming but integrate into v1 API**
- The legacy models system (Song, CampaignPlan) uses integer PKs and a different table naming scheme
- The new domain models (StudioSong, etc.) use UUID PKs and v1_* table naming
- The existing campaigns router is minimal and uses legacy models
- Decision: Extend the v1 API in backend/routers/v1.py with new marketing campaign endpoints that work with a new MarketingCampaign model in backend/domain/models.py (v1_marketing_campaigns table, UUID-based, following new patterns)
- This avoids polluting legacy models and keeps new features in the modern v1 API

**Key files discovered:**
- SongAnalysis.intelligence_json contains: audio_features, sections, hook_candidates, lyrics_analysis, predictions, limitations, provenance
- Ollama pattern: check enabled flag, use httpx client, graceful fallback on ConnectError/TimeoutException
- Database init: imports both models and domain_models, calls Base.metadata.create_all()
- No reportlab in requirements.txt — will need to add it

---

## Implementation Plan

- [ ] 1. Add reportlab to requirements.txt for PDF generation.
      Files: requirements.txt
      Verify: `pip install -r requirements.txt 2>&1 | grep -i reportlab` — confirms reportlab installed without errors.

- [ ] 2. Create MarketingCampaign model in backend/domain/models.py with UUID PK, owner_id, song_id FK, and JSON columns for campaign data, budget breakdown, captions, and posting schedule. Include relationships back to StudioSong.
      Files: backend/domain/models.py
      Verify: `cd backend && python -c "from domain.models import MarketingCampaign; print('MarketingCampaign imported successfully')"` — confirms model can be imported.

- [ ] 3. Create backend/services/budget_calculator.py with deterministic budget breakdown (no LLM). Implement allocate_budget(total_budget: float, goals: List[str]) -> dict returning channels with amount, percentage, objective, expected_deliverables, priority. Also implement zero_budget_organic_strategy() that returns a dict of organic tactics. Validate budget >= $100.
      Files: backend/services/budget_calculator.py
      Verify: Run `pytest tests/test_budget_calculator.py -v` (tests will be added by coder in verification step).

- [ ] 4. Create backend/services/campaign_planner.py with Ollama integration following the pattern in ollama_provider.py. Implement:
      - check_ollama_available() -> bool (try connection, handle error)
      - generate_song_quality_report(intelligence_json: dict, song: StudioSong) -> dict
      - generate_campaign_plan(intelligence_json: dict, song: StudioSong, budget: float, goals: list, target_audience: str, release_date: date) -> dict (pre-release, release-week, post-release sections)
      - generate_captions_and_concepts(intelligence_json: dict, song: StudioSong, target_platforms: list) -> dict (at least 10 per platform: Instagram, TikTok, Twitter/X, YouTube; includes video concepts, hooks, hashtags)
      - generate_posting_schedule(campaign_duration_days: int, release_date: date, num_posts: int) -> list[dict] (date, platform, content_type, caption_idea, call_to_action, required_assets, paid_promotion_budget)
      Split large prompts into sections (song analysis first, campaign plan, captions, schedule) to avoid Ollama context limit. Use only intelligence_json and provided inputs; never send audio bytes. Label estimates with "Estimated:" and AI opinions with "AI Assessment:". Validate JSON outputs before returning; retry once on parse failure. All return values are dicts (not models).
      Files: backend/services/campaign_planner.py
      Verify: Run `pytest tests/test_campaign_planner.py -v` — unit tests for each generate function pass.

- [ ] 5. Create backend/services/pdf_reporter.py using reportlab. Implement generate_campaign_pdf(campaign: MarketingCampaign, song: StudioSong, intelligence_json: dict, budget_breakdown: dict) -> bytes. PDF includes: executive summary, song analysis, strengths/weaknesses, genre positioning, campaign objectives & KPIs, itemized budget table, campaign timeline, captions & hooks, 4-week posting schedule table, performance tracking template, optimization recommendations, assumptions & limitations. Include page numbers, clean typography, currency formatting (USD), consistent section headers. Return bytes; do not write temp files.
      Files: backend/services/pdf_reporter.py
      Verify: Run `pytest tests/test_pdf_reporter.py::test_pdf_generation -v` — PDF is generated as bytes, is valid PDF, contains expected sections.

- [ ] 6. Create new IdempotencyRecord model in backend/domain/models.py for idempotent campaign creation (table v1_idempotency_records with idempotency_key, campaign_id, owner_id, created_at, expires_at). This ensures that duplicate POST /api/v1/campaigns requests with the same idempotency key return the same campaign.
      Files: backend/domain/models.py (append to existing file)
      Verify: Confirm model can be imported without errors.

- [ ] 7. Add new v1 API routes in backend/routers/v1.py (append new route functions at the end of the file before returning, or use a helper function approach):
      - POST /api/v1/campaigns (create campaign from song_id + inputs: budget, release_date, campaign_duration_days, target_audience, target_country, preferred_platforms, audience_size, goals, marketing_mix_preference; uses idempotency key from header Idempotency-Key; calls budget_calculator, campaign_planner, and pdf_reporter; persists to DB; returns full campaign JSON with status='draft' initially, runs background job to populate plan/captions/schedule, returns 201 with campaign object)
      - GET /api/v1/campaigns (list owner's campaigns, paginated 20/page, newest-first)
      - GET /api/v1/campaigns/{campaign_id} (fetch one campaign, owner-gated, full object)
      - GET /api/v1/campaigns/{campaign_id}/report.pdf (generate and stream PDF, owner-gated, Content-Disposition: attachment)
      - PATCH /api/v1/campaigns/{campaign_id} (update mutable fields: budget, goals, release_date, etc.; optionally regenerate with regenerate=true query param)
      - DELETE /api/v1/campaigns/{campaign_id} (delete, owner-gated)
      All routes use current_owner dependency. Routes return error 404 if campaign not found, 403 if not owner, 400 on validation error.
      Files: backend/routers/v1.py (append routes at end)
      Verify: Run `pytest tests/test_api_v1_campaigns.py -v` — unit tests for all 6 endpoints pass (using mock Ollama).

- [ ] 8. Update backend/database.py init_db() to ensure MarketingCampaign and IdempotencyRecord models are imported before Base.metadata.create_all(). Verify that the function imports both domain_models correctly.
      Files: backend/database.py
      Verify: Run `cd backend && python -c "from database import init_db; init_db(); print('Database initialized successfully')"` — no errors.

- [ ] 9. Add recharts to frontend package.json dependencies (npm install recharts). Create frontend/app/campaigns/new/page.tsx with song selector dropdown, budget slider ($100–$5000), release date picker, campaign_duration (default 28 days), target_audience text, target_country dropdown, preferred_platforms multi-select checkboxes, marketing_mix preference radio buttons, goals multi-select, audience_size optional input, submit button.
      Files: frontend/package.json, frontend/app/campaigns/new/page.tsx
      Verify: Run `cd frontend && npm install && npm run build` — build succeeds without errors.

- [ ] 10. Create frontend/app/campaigns/page.tsx (list all campaigns): fetch GET /api/v1/campaigns, display cards with song title, budget, release date, created date, link to detail. Include empty state if no campaigns.
      Files: frontend/app/campaigns/page.tsx
      Verify: Run `npm run build` — build succeeds; page renders without TypeScript errors.

- [ ] 11. Create frontend/app/campaigns/[id]/page.tsx (campaign detail): fetch GET /api/v1/campaigns/{id}, display song analysis summary (quality score, key insights from intelligence_json), budget breakdown pie/donut chart (recharts PieChart), campaign plan (accordion: pre-release / release-week / post-release), captions & content ideas (tabbed by platform), 4-week posting schedule (table view), PDF download button (GET /api/v1/campaigns/{id}/report.pdf), Edit / Regenerate / Delete buttons.
      Files: frontend/app/campaigns/[id]/page.tsx
      Verify: Run `npm run build` — build succeeds; page renders without TypeScript errors.

- [ ] 12. Update frontend navigation (check existing nav component in app/layout.tsx or components/, add link to /campaigns). Include a "Campaigns" menu item.
      Files: frontend/app/layout.tsx or components/nav.tsx (whichever exists)
      Verify: Run `npm run build` — build succeeds; nav includes Campaigns link.

- [ ] 13. Create backend/tests/test_budget_calculator.py with unit tests covering: successful allocation for small/medium/large budgets, budget < $100 raises error, zero_budget_organic_strategy returns dict with organic tactics, budget breakdown totals 100%.
      Files: backend/tests/test_budget_calculator.py
      Verify: Run `pytest tests/test_budget_calculator.py -v` — all tests pass.

- [ ] 14. Create backend/tests/test_campaign_planner.py with unit tests covering: check_ollama_available returns bool, generate_song_quality_report returns valid dict, generate_campaign_plan returns dict with pre/release/post sections, generate_captions_and_concepts returns dict with 10+ captions per platform, generate_posting_schedule returns list of 28 posts for 28-day campaign. Mock Ollama responses.
      Files: backend/tests/test_campaign_planner.py
      Verify: Run `pytest tests/test_campaign_planner.py -v` — all tests pass.

- [ ] 15. Create backend/tests/test_pdf_reporter.py with unit tests covering: generate_campaign_pdf returns bytes, PDF contains valid structure (headers, tables, page numbers), PDF includes all required sections (executive summary, budget table, schedule table, etc.).
      Files: backend/tests/test_pdf_reporter.py
      Verify: Run `pytest tests/test_pdf_reporter.py -v` — all tests pass.

- [ ] 16. Create backend/tests/test_api_v1_campaigns.py with integration tests covering: POST creates campaign, GET lists campaigns (pagination), GET /{id} fetches campaign, GET /{id}/report.pdf streams PDF, PATCH updates campaign, DELETE removes campaign, 404 on missing campaign, 403 on non-owner access, 400 on invalid budget.
      Files: backend/tests/test_api_v1_campaigns.py
      Verify: Run `pytest tests/test_api_v1_campaigns.py -v` — all integration tests pass.

- [ ] 17. Run full backend and frontend test suites and verify no regressions:
      Backend: `pytest tests/ -v --tb=short 2>&1 | tail -20` — all tests pass with no failures in test_* files.
      Frontend: `cd frontend && npm run build` — build succeeds without errors or TypeScript issues.
      Verify both pass, no breaking changes to existing features.

- [ ] 18. Manual verification and documentation:
      - Start backend: `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
      - Start frontend: `cd frontend && npm run dev`
      - Open browser to http://localhost:3000/campaigns
      - Create a test campaign with an existing song (if no songs, create one in /songs first)
      - Verify campaign is created and appears in the list
      - Click campaign to view details (song analysis, budget breakdown chart, campaign plan, captions, posting schedule should be visible)
      - Click "Download PDF" button, verify PDF downloads and contains expected sections
      - Test budget calculation: create campaign with $1000 budget, verify breakdown (Spotify 20%, TikTok 25%, Instagram/Meta 20%, YouTube 20%, Influencer 15%)
      - Verify Ollama integration: if Ollama is running locally (http://localhost:11434), campaigns should generate AI-powered content; if not available, should fall back gracefully to templates
      - Test budget < $100: attempt to create campaign with $50 budget, verify error message
      - Test campaign update: edit campaign budget, verify PATCH works and campaign updates
      - Test delete: delete a campaign, verify it no longer appears in list
      Verify: All manual tests pass without errors.

---

## Design Decisions

1. **MarketingCampaign model in domain/models.py (v1_marketing_campaigns table, UUID PK):**
   - Rationale: The new v1 API uses UUID PKs and domain models. Keeping the new feature in the same pattern maintains consistency. Legacy campaigns (backend/models.py CampaignPlan) is a separate task-planning feature; this is a distinct marketing campaign planner.

2. **Deterministic budget calculator (no LLM):**
   - Rationale: Budget allocation is deterministic math (no subjectivity). Keeping it in application code avoids sending budget data to Ollama and ensures consistency across runs. Ollama is used only for creative content (captions, posting strategy, hooks).

3. **Ollama pattern: replicate httpx client in campaign_planner.py instead of importing from ollama_provider.py:**
   - Rationale: Each service should be independent; ollama_provider focuses on YouTube metadata. Replicating the pattern (check enabled, httpx client, timeout/ConnectError handling) is cleaner than cross-service coupling.

4. **reportlab for PDF generation:**
   - Rationale: Pure Python library, no external executables needed, works on Windows/Linux/macOS. Allows PDF generation without writing temp files.

5. **Split large prompts in campaign_planner.py into sections:**
   - Rationale: Ollama Phi model has limited context (~2-4K tokens). Splitting song analysis, campaign plan, captions, and schedule into separate generations avoids context overflow and allows retry on individual sections.

6. **Frontend: recharts for budget pie chart:**
   - Rationale: Lightweight, React-native charting library. No need for external chart server.

7. **Idempotency via header-based request keys:**
   - Rationale: Prevents duplicate campaign creation if the user refreshes the form or retries due to network issues. Uses Idempotency-Key header pattern (common in API design).

8. **Routes in backend/routers/v1.py (not a separate file):**
   - Rationale: Keeps all v1 API endpoints in one place for easier discovery and maintenance. v1.py is already ~1100 lines; adding 200 lines for campaigns keeps related concerns together.

---

## Notes

- If Ollama is not running (localhost:11434), the campaign_planner will gracefully fall back to template-based content. No errors will be raised; users will see a note in the campaign that content was template-generated.
- PDF generation may take a few seconds for large reports; consider adding a background task if performance becomes an issue (not required for MVP).
- The posting schedule is currently fixed to a 28-day default; users can customize campaign_duration_days (e.g., 14, 30, 60 days) in the creation form.
- Captions and video concepts are tailored to the actual song (using intelligence_json, lyrics, genre) and target platforms; no generic suggestions.
- All currency formatting assumes USD. If international support is needed later, add a currency parameter to the campaign model and budget formatter.

