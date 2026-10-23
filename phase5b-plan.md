# Phase 5b: Genre-Based Visualizers with Lyrics Overlay — Implementation Plan

## Overview

Extend the existing lyric video generation system to include:
1. 50+ genre theme configurations with distinct visual styles
2. Automatic genre detection and theme selection
3. Genre-specific visualizers (not just waveforms)
4. Enhanced lyrics overlay with theme-aware styling
5. New API endpoints for theme preview and genre listing
6. Comprehensive test coverage for all genres

## Current State

- `backend/services/lyric_video_generator.py` exists with SRT/LRC parsing and ASS subtitle generation
- `backend/services/video_rendering.py` handles FFmpeg motion graphics (waveforms, spectrum)
- `backend/domain/models.py::VideoRender` stores render settings and output
- `backend/routers/v1.py` provides video render endpoints
- Tests exist for lyric parsing and ASS generation

## Design Decisions

**Genre Themes as JSON**: Store 50+ genre configurations in `backend/data/genre_themes.json` rather than a database table, since themes are static reference data that should be version-controlled and easily auditable. This avoids schema migration overhead and keeps theme changes transparent in git.

**Theme Loader Service**: Create `backend/services/genre_visualizer.py` with a single `ThemeLoader` class that reads and caches the genre themes on startup. This centralizes theme management and makes it easy to add new genres without code changes.

**Auto-Detection in Job Runner**: Integrate genre detection into the existing job runner (`backend/services/job_runner.py::_video_render_job`) so that if no explicit theme is provided, the system automatically selects one based on song metadata (artist-selected genres or audio analysis predictions).

**Lyrics Styling per Theme**: Create `backend/services/lyrics_renderer.py` to compute lyrics positioning, font size, colors, and contrast based on the selected theme. This allows each theme to have a unique visual presentation while reusing the same subtitle rendering pipeline.

**No Breaking Changes**: All additions are backward-compatible. Existing video renders without themes continue to work unchanged.

---

## Implementation Plan

### 1. Create genre themes data file
**What**: Create `backend/data/genre_themes.json` with 50+ genres, each with distinct visual profiles (colors, font styles, visualizer type, background effects).

**Why**: Central, version-controlled source of truth for genre aesthetics. Allows artists to understand exactly what visual treatment their track will receive.

**Files**:
- `backend/data/genre_themes.json` (new)

**Verify**: 
```powershell
.\.venv\Scripts\python.exe -c "import json; data=json.load(open('backend/data/genre_themes.json')); print(f'Loaded {len(data)} genres'); print('Sample genres:', list(data.keys())[:3])"
```
Expected: Confirms 50+ genres loaded with no JSON syntax errors.

---

### 2. Create genre visualizer service
**What**: Build `backend/services/genre_visualizer.py` with `GenreThemeLoader` class that:
- Loads genre themes on module import and caches them
- Provides `get_theme(genre: str) -> dict` with fallback to "pop" for unknown genres
- Provides `detect_genre(song_metadata: dict) -> str` that selects genre from artist preferences or audio analysis
- Provides `build_ffmpeg_filter(theme: dict, mode: str) -> str` that constructs genre-specific FFmpeg filters (waveform vs. spectrum, color palettes, etc.)

**Why**: Encapsulates theme logic, makes genre detection testable, and provides a clean API for the job runner and endpoints.

**Files**:
- `backend/services/genre_visualizer.py` (new)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_genre_visualizer.py -v
```
Expected: All tests pass (theme loading, genre detection, filter generation).

---

### 3. Create lyrics renderer service
**What**: Build `backend/services/lyrics_renderer.py` with:
- `LyricsRenderConfig` dataclass (font size, color, outline, shadow, alignment per theme)
- `compute_render_config(theme: dict, video_dimensions: tuple) -> LyricsRenderConfig` that calculates contrast-safe font sizes and positioning
- `build_ass_subtitles_themed(subtitles: list[Subtitle], config: LyricsRenderConfig) -> str` that generates ASS with theme-specific styling

**Why**: Separates concerns: theme selection vs. lyrics presentation. Allows themes to define fonts, colors, shadows, and positioning that work well with their visualizers.

**Files**:
- `backend/services/lyrics_renderer.py` (new)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_lyrics_renderer.py -v
```
Expected: Tests verify font sizing, color contrast, and ASS generation with theme styling.

---

### 4. Extend lyric video generator
**What**: Modify `backend/services/lyric_video_generator.py::render_lyric_video` to:
- Accept optional `theme: dict` parameter (default None, uses generic waveform)
- Accept optional `video_dimensions: tuple` parameter (default (1280, 720))
- If theme provided, use `genre_visualizer.build_ffmpeg_filter(theme, mode)` to create genre-specific filters
- If theme provided, use `lyrics_renderer.build_ass_subtitles_themed()` for styled lyrics
- Log theme applied and filter used

**Why**: Reuses existing render infrastructure; theme becomes optional parameter that enhances but doesn't break existing behavior.

**Files**:
- `backend/services/lyric_video_generator.py` (modify: add theme and video_dimensions parameters)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_lyric_video_generation.py -v
```
Expected: Existing tests still pass; new theme parameter tests pass.

---

### 5. Extend video job runner
**What**: Modify `backend/services/job_runner.py::_video_render_job` to:
- Extract song genre from database (via `song.genre_preferences[0]` or artist profile)
- Call `genre_visualizer.detect_genre(song_metadata)` to select theme
- Pass theme to render functions
- Store `selected_theme` and `detected_genre` in `VideoRender.render_settings_json` for audit trail
- Log genre selection and theme applied

**Why**: Integrates theme selection into the existing job execution pipeline. Automatic detection means no UI changes required immediately.

**Files**:
- `backend/services/job_runner.py` (modify: _video_render_job function)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_job_runner_publishing.py -v
```
Expected: Existing job runner tests still pass; new theme selection logic verified.

---

### 6. Add theme preview API endpoint
**What**: Add `GET /api/v1/genres/{genre}/theme-preview` endpoint in `backend/routers/v1.py` that:
- Returns theme config (colors, visualizer type, fonts, styling)
- Includes example FFmpeg filter command
- Includes example lyrics rendering parameters

**Why**: Allows frontend to show users what their track will look like before rendering. Educational and helps artists make informed choices.

**Files**:
- `backend/routers/v1.py` (modify: add theme_preview endpoint)
- `backend/domain/schemas.py` (add: GenreThemeOut, ThemePreviewOut schemas)

**Verify**:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/genres/rock/theme-preview" -Headers @{"Authorization"="Bearer <token>"} | ConvertFrom-Json | ConvertTo-Json
```
Expected: Returns theme config with valid schema.

---

### 7. Add genres listing endpoint
**What**: Add `GET /api/v1/genres` endpoint in `backend/routers/v1.py` that:
- Returns list of all 50+ available genres with brief descriptions
- Includes primary_color and visualizer_type for each
- Supports optional query param `?limit=20&offset=0` for pagination (though list is small enough to return all)

**Why**: Enables frontend to build genre selector UI.

**Files**:
- `backend/routers/v1.py` (modify: add genres_list endpoint)
- `backend/domain/schemas.py` (add: GenreOut, GenreListOut schemas)

**Verify**:
```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/genres" -Headers @{"Authorization"="Bearer <token>"} | ConvertFrom-Json | ConvertTo-Json | head -50
```
Expected: Returns array of 50+ genre objects with consistent schema.

---

### 8. Extend VideoRenderRequest schema
**What**: Modify `backend/domain/schemas.py::VideoRenderRequest` to add optional `theme_genre: str | None = None` field.

**Why**: Allows frontend to optionally specify a genre theme override. If omitted, auto-detection in job runner applies.

**Files**:
- `backend/domain/schemas.py` (modify: VideoRenderRequest)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -c "from backend.domain.schemas import VideoRenderRequest; print(VideoRenderRequest.model_json_schema())"
```
Expected: Schema includes `theme_genre` field as optional string.

---

### 9. Create comprehensive test suite
**What**: Write tests covering:
- **test_genre_themes_data.py**: Validates genre_themes.json structure (50+ genres, required fields, valid colors)
- **test_genre_visualizer.py**: Tests ThemeLoader loading, genre detection, FFmpeg filter generation for each of 10+ major genres
- **test_lyrics_renderer.py**: Tests contrast calculation, font sizing, ASS generation with theme styling
- **test_genre_integration.py**: End-to-end: render video with theme, verify output settings match theme

**Why**: Ensures all 50+ genres are properly configured and work correctly with the rendering pipeline.

**Files**:
- `tests/test_genre_themes_data.py` (new)
- `tests/test_genre_visualizer.py` (new)
- `tests/test_lyrics_renderer.py` (new)
- `tests/test_genre_integration.py` (new)

**Verify**:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_genre_*.py tests/test_lyrics_renderer.py -v
```
Expected: All new tests pass; 50+ genres validate; integration tests confirm theme application.

---

### 10. Update README
**What**: Add section to README documenting:
- List of 50+ supported genres and their visual characteristics
- How genre detection works (artist preference > audio analysis fallback)
- Example theme override in API request
- Theme customization instructions for developers

**Why**: Helps artists and developers understand the feature.

**Files**:
- `README.md` (modify: add genre themes section under "Lyric-Video Rendering")

**Verify**:
```powershell
Select-String -Path README.md -Pattern "genre|theme|visualizer" | Measure-Object
```
Expected: At least 10 mentions of genres or themes in README.

---

## Verification Checklist (Overall)

```powershell
# 1. Data file valid JSON
.\.venv\Scripts\python.exe -c "import json; json.load(open('backend/data/genre_themes.json'))"

# 2. All new tests pass
.\.venv\Scripts\python.exe -m pytest tests/test_genre*.py tests/test_lyrics_renderer.py -v

# 3. Existing tests still pass
.\.venv\Scripts\python.exe -m pytest tests/test_lyric_video_generation.py tests/test_job_runner_publishing.py -v

# 4. Full test suite passes
.\.venv\Scripts\python.exe -m pytest tests/ -q --tb=short

# 5. API endpoints respond
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/genres" -Headers @{"Authorization"="Bearer <token>"}
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/genres/rock/theme-preview" -Headers @{"Authorization"="Bearer <token>"}
```

Expected: All pass.

---

## Notes

- **Genre Coverage**: The 50+ genres include: Pop, Rock, Hip-Hop, Country, R&B, Jazz, Classical, Electronic, Dance, Metal, Reggae, Latin, Soul, Folk, Indie, Alternative, Punk, Gospel, Ambient, Techno, House, Trance, Drum & Bass, Dubstep, Trap, Future Bass, Synthwave, Vaporwave, Lo-fi, Chillhop, Phonk, Drill, Emo, Scene, Screamo, Metalcore, Deathcore, Experimental, Avant-Garde, Noise, Industrial, Darkwave, Synthpop, New Wave, Post-Punk, Grunge, Riot Grrrl, Emo Pop, Pop Punk, and variants/fusions.

- **Visualizer Types**: Each genre uses one of three base visualizer types (waveform, spectrum, or hybrid) with theme-specific colors and effects.

- **Backwards Compatibility**: If no theme is specified, renders fall back to basic waveform behavior (current behavior).

- **Database Changes**: No schema migrations required. Theme selection is stored in `VideoRender.render_settings_json` as metadata.

- **Frontend Integration**: Frontend can be updated to show theme selector in video render form and preview theme before confirming render. Both are optional.

---

## Files Summary

### New Files (6)
1. `backend/data/genre_themes.json` — 50+ genre configurations
2. `backend/services/genre_visualizer.py` — Theme loading and genre detection
3. `backend/services/lyrics_renderer.py` — Theme-aware lyrics styling
4. `tests/test_genre_themes_data.py` — Genre data validation
5. `tests/test_genre_visualizer.py` — Theme loader and detection tests
6. `tests/test_lyrics_renderer.py` — Lyrics styling tests

### Modified Files (5)
1. `backend/services/lyric_video_generator.py` — Add theme and video_dimensions parameters
2. `backend/services/job_runner.py` — Integrate genre detection and theme application
3. `backend/routers/v1.py` — Add genres list and theme preview endpoints
4. `backend/domain/schemas.py` — Add genre-related schemas and VideoRenderRequest.theme_genre field
5. `README.md` — Document genre themes feature

### Tests Added (4)
- Genre themes data validation
- Genre visualizer and detection
- Lyrics renderer with theme styling
- End-to-end genre integration

