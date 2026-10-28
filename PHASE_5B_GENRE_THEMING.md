# Phase 5b: Enhanced Genre-Themed Lyrics Visualizer

> Contributor: deepakrathod750

## Overview

Phase 5b enhances the video rendering system with genre-aware theming and always-visible lyrics overlay. Songs now render with visualizers and lyrics that adapt to the musical genre, providing a professional music video experience tailored to each track's style.

## Features

### 1. Genre Dataset

**File**: `backend/data/genre_themes.json`

Contains 50+ music genres with complete visualization and styling configurations:

```json
{
  "electronic": {
    "visualizer_type": "spectrum",
    "colors": ["#00FF00", "#00FFFF", "#FF00FF"],
    "tempo_sync": true,
    "lyrics_position": "bottom",
    "lyrics_font_family": "Arial",
    "lyrics_font_size": 36,
    "background_color": "#000000"
  },
  ...
}
```

**Supported Genres (50+)**:
- Electronic music: electronic, house, techno, trance, drum&bass, dubstep, synthwave
- Hip-hop & rap: hip-hop, trap, reggaeton, afrobeat
- Rock & metal: rock, metal, punk, grunge, post-punk, emo, alternative
- Pop: pop, k-pop, j-pop, anime
- Urban & dance: funk, disco, regga­e, salsa, samba, latin
- Jazz & blues: jazz, blues, soul
- Classical & orchestral: classical, orchestral, opera, cinematic, trailer
- Acoustic: acoustic, folk, singer-songwriter, bossa-nova, celtic
- Ambient & experimental: ambient, lo-fi, ambient-electronica, chillwave, vaporwave, trip-hop, industrial, darkwave
- World music: world, balkan, klezmer, flamenco, tango, cumbia, merengue
- Bonus: video-game, orchestral, cinematic, trailer music

### 2. Genre Visualizer Service

**File**: `backend/services/genre_visualizer.py`

```python
class GenreVisualizer:
    def load_genre_theme(genre: str) -> GenreThemeConfig:
        """Load theme configuration for genre"""
    
    def get_all_genres() -> list[str]:
        """List all 50+ supported genres"""
    
    def detect_genre_from_metadata(song_metadata, genre_preferences) -> str:
        """Auto-detect genre from audio features or user preferences"""
    
    def get_ffmpeg_filters(theme: GenreThemeConfig, duration: float) -> str:
        """Generate FFmpeg filter chain for visualizer"""
    
    def validate_theme_contrast(text_color, bg_color) -> bool:
        """Ensure text color contrasts with background (WCAG AA)"""
```

**Features**:
- Load pre-configured genres with visual styling
- Auto-detect genre from audio features (energy, danceability, acousticness)
- Generate genre-specific FFmpeg filters (waveform vs spectrum)
- Validate typography contrast for accessibility

### 3. Lyrics Renderer Service

**File**: `backend/services/lyrics_renderer.py`

```python
class LyricsRenderer:
    def render_lyrics_always_visible(
        lyrics: list[dict],
        duration: float,
        theme: GenreThemeConfig
    ) -> str:
        """Generate FFmpeg drawtext command for always-visible lyrics
        - Lyrics remain visible throughout entire video
        - Sync to audio timing with enable expressions
        - Position based on genre theme (top, bottom, center, flowing)
        - Colors contrast with visualizer background
        """
    
    def validate_lyrics_readability(
        font_size: int,
        bg_color: str,
        text_color: str
    ) -> bool:
        """Ensure sufficient contrast and readable font size"""
    
    def format_lyrics_for_timing(
        raw_lyrics: str,
        start_time_ms: int = 0
    ) -> list[dict]:
        """Format raw lyrics into timed objects with start/end milliseconds"""
    
    def build_lyrics_filter_chain(
        lyrics: list[dict],
        duration: float,
        theme: GenreThemeConfig,
        visualizer_filter: str
    ) -> str:
        """Combine visualizer and lyrics into single FFmpeg filter chain"""
```

**Features**:
- Always-visible lyrics with timing synchronization
- No gaps or hidden text during playback
- FFmpeg enable expressions for precise timing
- Genre-aware positioning and styling
- WCAG-compliant contrast validation

### 4. Data Models

**File**: `backend/domain/schemas.py`

New Pydantic models:

```python
class GenreThemeConfig(BaseModel):
    genre: str
    visualizer_type: Literal["waveform", "spectrum"]
    colors: list[str]
    lyrics_position: Literal["top", "bottom", "center", "flowing"]
    lyrics_font_family: str
    lyrics_font_size: int  # 24-96
    tempo_sync: bool
    background_color: str

class LyricsRenderConfig(BaseModel):
    lyrics: list[dict]  # [{text, start_ms, end_ms}, ...]
    always_visible: bool = True
    position: Literal["top", "bottom", "center", "flowing"]
    font_size: int  # 24-96
    color: str
    background_color: str

class VideoGenreTunedRenderRequest(BaseModel):
    asset_id: str
    genre: str | None = None
    lyrics: str | None = None
    lyrics_format: Literal["plain", "srt", "lrc"] = "plain"
    render_format: Literal["music_visualizer", "full_music_video"] = "music_visualizer"

class VideoGenreTunedRenderOut(VideoRenderOut):
    genre: str | None = None
    lyrics_visible: bool = True
```

### 5. API Endpoints

**New Endpoints in `/api/v1`**:

#### Get All Supported Genres

```
GET /api/v1/video/genres
```

Response:
```json
{
  "total_genres": 54,
  "genres": {
    "electronic": {
      "genre": "electronic",
      "visualizer_type": "spectrum",
      "colors": ["#00FF00", ...],
      "lyrics_position": "bottom",
      ...
    },
    ...
  }
}
```

#### Preview Genre Theme

```
POST /api/v1/video/preview-theme?genre=hip-hop
```

Response:
```json
{
  "genre": "hip-hop",
  "visualizer_type": "waveform",
  "primary_color": "#FFD700",
  "secondary_colors": ["#FF6347", "#000000"],
  "lyrics_position": "center",
  "lyrics_font_size": 42,
  "background_color": "#1a1a1a",
  "tempo_sync": true
}
```

#### Generate Genre-Themed Lyric Video

```
POST /api/v1/songs/{song_id}/video-renders-themed
  ?asset_id=...
  &genre=hip-hop
  &lyrics=<url-encoded lyrics>
```

Request:
```bash
curl -X POST "http://localhost:8000/api/v1/songs/{song_id}/video-renders-themed" \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: <unique-key>" \
  -d "asset_id=abc123" \
  -d "genre=hip-hop" \
  -d "lyrics=Yeah%20I%20got%20rhythm..."
```

Response (202 Accepted):
```json
{
  "render_id": "render_xyz",
  "song_id": "song_abc",
  "asset_id": "asset_123",
  "job_id": "job_456",
  "render_format": "music_visualizer",
  "status": "queued",
  "stage": "queued",
  "progress_percent": 0,
  "scene_plan": [...],
  "render_settings": {
    "genre": "hip-hop",
    "visualizer_type": "waveform",
    "lyrics_visible": true
  },
  "status_url": "/api/v1/video-renders/render_xyz",
  "download_url": null
}
```

## Usage Examples

### Example 1: List All Genres

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/video/genres",
    headers={"Authorization": "Bearer <token>"}
)
genres = response.json()
print(f"Available genres: {list(genres['genres'].keys())}")
```

### Example 2: Auto-Detect and Render

```python
# Genre auto-detection from user preferences
response = httpx.post(
    "http://localhost:8000/api/v1/songs/song_123/video-renders-themed",
    headers={"Authorization": "Bearer <token>"},
    params={
        "asset_id": "audio_456",
        # genre not specified - will auto-detect from song metadata
        "lyrics": "Verse 1\nChorus\nVerse 2"
    }
)
render = response.json()
print(f"Rendering {render['render_id']} - genre: {render['render_settings']['genre']}")
```

### Example 3: Genre Theme Preview

```python
response = httpx.post(
    "http://localhost:8000/api/v1/video/preview-theme",
    params={"genre": "k-pop"}
)
theme = response.json()
print(f"K-pop theme: {theme['visualizer_type']} @ {theme['lyrics_position']}")
print(f"Colors: {theme['primary_color']}, {theme['secondary_colors']}")
```

### Example 4: Genre Detection from Metadata

```python
from backend.services.genre_visualizer import detect_genre_from_metadata

# From user's genre preferences
genre = detect_genre_from_metadata(
    {},
    genre_preferences=["hip-hop", "trap"]
)
# Returns: "hip-hop"

# From audio features
metadata = {
    "audio_features": {
        "energy": {"value": 0.9, "status": "measured"},
        "acousticness": {"value": 0.1, "status": "measured"}
    }
}
genre = detect_genre_from_metadata(metadata)
# Returns: "metal" (high energy, low acousticness)
```

## Architecture

### Data Flow

```
User Song + Metadata + Lyrics
    ↓
Genre Detection (from user preferences or audio features)
    ↓
Load Genre Theme Configuration (colors, visualizer type, lyrics position)
    ↓
Format Lyrics with Timing (start_ms, end_ms for each line)
    ↓
Build FFmpeg Filters:
  - Visualizer filter (spectrum/waveform)
  - Lyrics drawtext filter (always-visible, timed)
  ↓
FFmpeg renders MP4:
  Input: Audio file
  Filters: visualizer + lyrics overlay
  Output: 1280x720 H.264/AAC MP4 with synced lyrics
```

### Genre → Visualizer Mapping

| Genre | Visualizer | Position | Colors | Tempo Sync |
|-------|-----------|----------|--------|-----------|
| electronic | spectrum | bottom | cyan, magenta | yes |
| hip-hop | waveform | center | gold, crimson | yes |
| rock | spectrum | bottom | red, white | yes |
| ambient | waveform | top | blue, light blue | no |
| jazz | spectrum | top | brown, gold | no |
| classical | waveform | top | gold, white | no |
| pop | waveform | bottom | pink, sky blue | yes |
| metal | spectrum | center | red, white | yes |

## Testing

**Test Files**:
- `tests/test_genre_visualizers.py`: 40+ tests for genre loading, detection, filtering
- `tests/test_lyrics_rendering.py`: 50+ tests for lyrics formatting, rendering, timing

**Test Coverage**:

```bash
# Run all Phase 5b tests
pytest tests/test_genre_visualizers.py tests/test_lyrics_rendering.py -v --tb=short

# Test genre loading
pytest tests/test_genre_visualizers.py::TestGenreThemeLoading -v

# Test lyrics rendering
pytest tests/test_lyrics_rendering.py::TestLyricsRendering -v

# Test contrast validation
pytest tests/test_genre_visualizers.py::TestThemeContrast -v
```

**Key Test Scenarios**:
- Load 50+ genres successfully
- Auto-detect genre from audio features
- Generate FFmpeg filter chains
- Validate text contrast (WCAG AA)
- Format lyrics with timing
- Render always-visible lyrics
- Handle edge cases (empty lyrics, invalid genres, special characters)

## Implementation Details

### Genre Auto-Detection Algorithm

Priority order:
1. **User preference** (from `genre_preferences` list)
2. **Audio features analysis**:
   - Acousticness > 0.7 → acoustic
   - Danceability > 0.75 → electronic
   - Energy > 0.8 → metal
   - Energy < 0.3 → ambient
   - Danceability > 0.6 → house
3. **Fallback** → electronic

### Lyrics Always-Visible Implementation

- Each lyric line uses FFmpeg `drawtext` filter
- Timing controlled by `enable` expression: `gte(t,start_sec)*lte(t,end_sec)`
- Text color auto-selected based on background brightness
- Border and shadow for readability across visualizers
- Position dynamically set from genre config (top, bottom, center, flowing)

### FFmpeg Filter Chain Example

```ffmpeg
-filter_complex "[0:a]showwaves=s=1280x720:mode=line:rate=30:colors=0xFFD700:scale=sqrt,
drawtext=text='Verse 1':fontsize=42:x=(w-text_w)/2:y=h*0.5:enable='gte(t,0)*lte(t,2)',
drawtext=text='Chorus':fontsize=42:x=(w-text_w)/2:y=h*0.5:enable='gte(t,2)*lte(t,5)'[v]"
```

## Limitations & Future Work

### Current Limitations
- Lyrics manually provided (not auto-extracted from audio)
- Lyrics timing manual (not auto-synced to audio)
- Genre detection based on simple heuristics (not ML model)
- Limited to 1280x720 resolution
- No support for multi-color text or animations

### Future Enhancements
- Speech-to-text lyrics extraction from audio
- Automatic lyrics-to-beat synchronization
- ML-based genre classification from audio
- Support for 4K rendering
- Animated text effects based on genre
- Karaoke mode (word-by-word highlighting)
- Multiple language support
- Real-time lyrics positioning adjustment

## Accessibility

- **WCAG AA Contrast**: All text colors validated for 4.5:1 contrast ratio
- **Font Size**: Minimum 24px, maximum 96px for readability
- **Position**: Multiple positioning options (top, bottom, center) for flexibility
- **Timing**: Precise millisecond-level synchronization for accurate playback

## Performance

- Genre theme loading: cached in memory after first load
- FFmpeg rendering: standard profile (veryfast preset, 23 CRF)
- File size: typical 2-5 MB for 3-minute song at 720p 30fps
- Render time: ~30-60 seconds for 3-minute song on modern CPU

## Schema Version

- Phase 5b schema: `v1_genre_theming_2024`
- Backward compatible with Phase 5 video renders
- New `render_settings.genre` and `render_settings.lyrics_visible` fields

## Configuration

No additional configuration required. Genre themes are embedded in `genre_themes.json`.

Optional environment variables (if extending):
```bash
# Future: custom genre config path
GENRE_THEMES_PATH=/path/to/custom/genres.json

# Future: max lyrics per video
MAX_LYRICS_LINES=1000
```

## Troubleshooting

### Genre Not Found
- Falls back to "electronic"
- Check genre name is lowercase, hyphen-separated
- Valid example: "hip-hop", "k-pop", "j-pop", "video-game"

### Lyrics Not Visible in Video
- Ensure lyrics text is not empty
- Check contrast ratio (use `validate_lyrics_readability()`)
- Verify font size is 24-96 px
- Ensure timing start < end and within video duration

### FFmpeg Errors
- Verify FFmpeg is installed: `ffmpeg -version`
- Check ffprobe available: `ffprobe -version`
- Ensure audio file is valid WAV/MP3/M4A

## References

- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html#drawtext-1)
- [WCAG 2.1 Contrast Requirements](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [LRC Lyrics Format](https://en.wikipedia.org/wiki/LRC_(file_format))
- [SRT Subtitle Format](https://en.wikipedia.org/wiki/SubRip)
