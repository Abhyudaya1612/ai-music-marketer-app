# Phase 5b Requirements: Genre-Based Themed Lyric Videos with Always-Visible Lyrics

> Contributor: deepakrathod750

## Summary

Extend the existing lyric video generation system to move beyond static waveform/spectrum visualizers and create rich, genre-specific themed lyric videos where lyrics are always visible throughout the entire video duration. Each of 50+ music genres receives a tailored visual theme with unique color palettes, visualizer effects, animation styles, and typography. Videos will synchronize lyrics to audio timing with large, readable text that never disappears, styled appropriately for each genre's aesthetic.

## Functional Requirements

### 1. Comprehensive Genre-to-Theme Mapping
- Create a dataset mapping 50+ music genres to visual themes
- Each genre has:
  - **Visualizer type** (e.g., neon particles, beat-sync geometry, organic flows)
  - **Primary and secondary colors** with hex values
  - **Accent color** for contrast with lyrics
  - **Animation style** (tempo-synced or static fixed speed)
  - **Typography** (font family, size, positioning within frame)
  - **FFmpeg filter chain** for rendering the visualizer
- Store complete mapping in `backend/data/genre_themes.json`
- Minimum genres: electronic, hip-hop, trap, rock, metal, pop, dance-pop, jazz, ambient, lo-fi, classical, orchestral, folk, acoustic, indie, reggae, country, Americana, R&B, soul, Latin, reggaeton, dubstep, house, techno, drum-and-bass, indie-rock, alternative, punk, grunge, blues, gospel, funk, disco, synth-pop, new-wave, post-punk, emo, metalcore, progressive-metal, symphonic-metal, black-metal, death-metal, thrash-metal, experimental, ambient-electronic, trip-hop, downbeat, chill-hop, vaporwave, synthwave, k-pop

### 2. Always-Visible Lyrics
- Lyrics text appears throughout entire video duration, never hidden or faded away
- Lyrics remain synchronized to audio timing from parsed timing data (SRT, LRC, or word-level timings)
- Position varies by genre theme:
  - **Center overlay** for pop, dance, trap
  - **Bottom scroll/crawl** for electronic, techno
  - **Top positioned** for classical, orchestral
  - **Flowing/animated path** for indie, indie-rock
  - **Karaoke-style highlight** optional for all (current word/line highlighted distinctly)
- Font size large enough for legibility at 1280×720 resolution (minimum 28px, typical 36-48px)
- Text color contrasts with background visualizer (typically white, light colors, or genre-specific accent color)
- Text strokes/shadows for readability over varying background intensity

### 3. Visualizer Types (Genre-Specific)
- **Neon Particles**: Electronic, synth-pop, synthwave — floating/orbiting points with trails
- **Beat-Sync Geometric**: Hip-hop, trap, drum-and-bass — rectangles/circles that respond to beat/kick
- **Distorted Waves**: Rock, metal, alternative — wavy/jagged FFmpeg showwaves with high amplitude
- **Bouncing Shapes**: Pop, dance-pop, house, disco — animated circles/squares that move to audio energy
- **Smooth Flowing**: Jazz, ambient, lo-fi, downtempo — gentle curved lines or flow fields
- **Elegant Patterns**: Classical, orchestral, symphonic — symmetric kaleidoscopic or mandala patterns
- **Organic Nature**: Folk, acoustic, indie, indie-rock — leaf/nature-inspired particles or wood texture overlays
- **Smooth Waves**: Reggae, island music — gentle rolling wave motion
- **Rustic/Barn**: Country, Americana, folk — wood texture, lasso/rope patterns, retro film grain
- **Silky Smooth**: R&B, soul, gospel — soft color gradients with subtle radial motion
- **Spectrum Burst**: Dubstep, bass music — FFmpeg showspectrum with high-frequency emphasis and glow
- **Grid/Laser**: Techno, house, synthwave — grid lines, laser beams, geometric intersections
- **Chromatic Aberration**: Experimental, vaporwave, glitch — color-shifted distorted waves or particle clouds
- **Minimal Pulse**: Chill-hop, lo-fi, ambient-electronic — single pulsing circle or soft expanding rings

### 4. Lyric Positioning and Styling per Genre
- **Pop/Dance/Trap**: Center-aligned, bold sans-serif, white text with subtle black outline
- **Rock/Metal**: Center or slightly offset, aggressive/angular font, color matching genre (red/white for rock, dark/white for metal)
- **Classical/Orchestral**: Top-left or top-center, serif font (e.g., Georgia, serif), elegant light colors
- **Jazz/Ambient/Lo-Fi**: Bottom-right or floating center, cursive or humanist sans-serif, warm colors (gold, cream)
- **Electronic/Synth-Pop**: Center or scrolling bottom, monospace or geometric sans-serif, neon accent colors
- **Folk/Indie**: Slightly offset left/right, handwriting-style font, earthy colors (green, brown, cream)
- **Country/Americana**: Bottom or lower-third, rustic/western-style font, gold/tan text
- **R&B/Soul**: Lower-center, smooth rounded sans-serif, warm colors (magenta, gold, cream)
- **Reggae**: Center-lower, bold sans-serif, bright colors (yellow, green, red matching flag)
- **Experimental**: Dynamic positioning, colors shift with audio, possibly animated text scaling

### 5. Color Palettes (Each Genre)
Each genre entry specifies:
- `primary_color`: Hex value (e.g., "#00FF00") — dominant visualizer color
- `secondary_color`: Hex value — accent for particles or background layers
- `accent_color`: Hex value — for lyric text contrast
- `background_color`: Hex value or "dark"/"light" — video background (default black/dark for most)

Example structure:
```json
{
  "electronic": {
    "primary_color": "#00FF00",
    "secondary_color": "#FF00FF",
    "accent_color": "#00FFFF",
    "background_color": "#0a0a0a"
  },
  "hip-hop": {
    "primary_color": "#FFD700",
    "secondary_color": "#000000",
    "accent_color": "#FFFFFF",
    "background_color": "#1a1a1a"
  }
}
```

### 6. Animation Speeds and Tempo-Sync
- **Tempo-synced genres** (hip-hop, trap, dance, electronic, house, techno): Particle/shape movement and transitions tied to detected BPM
  - Extract BPM from audio using FFprobe or Librosa
  - Map BPM to animation frame rate and effect intensity
- **Static-speed genres** (jazz, ambient, classical, folk): Fixed animation speed regardless of BPM (e.g., 30fps consistent motion)
- Fallback: If BPM unavailable, use default speed for the visualizer type

### 7. Typography Details
Each genre specifies:
- `font_family`: e.g., "Arial", "Georgia", "Courier New", "Comic Sans MS", "Impact"
- `font_size`: Default size in pixels (e.g., 42)
- `font_weight`: "normal", "bold", or numeric (400, 700, etc.)
- `text_positioning`: "center", "bottom", "top", "left", "right", "scroll", "karaoke"
- `text_stroke_width`: Outline thickness for readability (0-3 pixels, typical 1-2)
- `text_stroke_color`: Outline color for legibility

### 8. FFmpeg Integration
- Each visualizer type maps to an FFmpeg filter chain
- Examples:
  - Waveform: `showwaves=s=1280x720:colors=0xFFFFFF`
  - Spectrum: `showspectrum=s=1280x720:colors=cool`
  - Complex chains may use `filter_complex` with multiple inputs/layers
- Subtitle overlay persists throughout video using ASS format (already implemented in current `lyric_video_generator.py`)
- Video output: H.264/AAC MP4, 1280×720 resolution

## Non-Functional Requirements

### Performance
- Lyric video render completes within 120 seconds for typical 3-5 minute tracks
- Genre theme lookup is O(1) dictionary access
- No repeated parsing of genre themes during batch operations

### Testability
- Genre theme JSON validates against a schema
- Each visualizer type can be tested independently with synthetic audio
- Lyric positioning can be tested with fixed-size frames
- Render operations are unit-testable by mocking FFmpeg calls

### Maintainability
- Genre themes stored in JSON for easy updates and additions without code changes
- Visualizer type definitions are self-documenting (font names, colors are self-evident)
- Clear separation: genre dataset, visualizer implementations, lyric rendering logic

## Acceptance Criteria

1. **Genre Dataset Complete**
   - [ ] `backend/data/genre_themes.json` created with 50+ genres
   - [ ] Each genre includes: visualizer_type, primary_color, secondary_color, accent_color, background_color, font_family, font_size, font_weight, text_positioning, text_stroke_width, text_stroke_color, tempo_sync (boolean)
   - [ ] JSON validates against a defined schema with no syntax errors
   - [ ] All colors are valid hex values
   - [ ] All font families are system-available or safe web fonts

2. **Lyric Video Generator Enhanced**
   - [ ] `render_lyric_video()` function accepts optional `genre` parameter
   - [ ] When genre is provided, visualizer type and colors are selected from theme dataset
   - [ ] Lyrics remain visible throughout entire video duration (not faded or hidden)
   - [ ] Lyric positioning respects genre-specific `text_positioning` rule
   - [ ] Lyric text color uses genre `accent_color` for contrast
   - [ ] Text stroke applied for readability

3. **Audio Detection**
   - [ ] BPM extraction working for tempo-synced genres
   - [ ] Fallback to default speed if BPM unavailable
   - [ ] BPM correctly influences animation speed (faster BPM = faster particles/movements)

4. **FFmpeg Filter Chains**
   - [ ] Each of 13 visualizer types has a working FFmpeg filter chain
   - [ ] Filter chains produce correct visual output (verified by inspecting rendered frames)
   - [ ] No FFmpeg errors during render for any visualizer type

5. **Video Output Quality**
   - [ ] Output videos are exactly 1280×720 resolution
   - [ ] Lyrics clearly readable in rendered output (font size, contrast, no clipping)
   - [ ] Karaoke-style highlighting (if enabled) correctly highlights current word/line
   - [ ] All genre-themed videos render without errors

6. **API Integration**
   - [ ] `/api/v1/lyric-video/render` endpoint accepts `genre` parameter (optional)
   - [ ] Endpoint returns valid video with genre theme applied
   - [ ] API documentation updated with genre parameter and available genres list

7. **End-to-End Test**
   - [ ] Full workflow: upload song → analyze → extract genre → generate themed lyric video
   - [ ] Tested with at least 3 different genres from different families (e.g., electronic, rock, classical)
   - [ ] Lyrics sync to audio timing accurately
   - [ ] Lyrics remain visible throughout entire video

## Out of Scope

- AI-generated artwork or cinematic video footage (only music visualizers)
- Real-time live performance lyric display
- Multi-language lyric support (English primary; other languages subject to font availability)
- Video publishing or platform distribution (videos remain in private storage)
- User interface for selecting/customizing genre themes (themes are pre-built in dataset)
- Automatic genre detection from audio (genre must be provided by user or extracted from metadata)
- Complex layered 3D visualizations (2D FFmpeg filters only)
- Synchronized backing-track overlay (original audio only, no instrumental/acapella mixing)
- Detailed timeline editing for individual lyric lines in UI (SRT/LRC format parsing only)
- DRM or copy-protection mechanisms
- Social media export or sharing workflows
- Performance analytics or engagement metrics for rendered videos

## Assumptions

1. **Genre metadata available**: The system has access to song genre (either user-provided or from music metadata)
2. **FFmpeg/FFprobe installed**: Current project already requires FFmpeg; this feature does not introduce new external dependencies
3. **System fonts available**: Standard fonts (Arial, Georgia, Courier) available on render server (Windows, Linux, macOS)
4. **Audio format support**: Input audio is MP3, WAV, or AAC (already validated by project's audio handling)
5. **Lyric timing accurate**: Provided SRT/LRC timing data is reasonably accurate and synced to audio
6. **Render capacity**: Single-threaded FFmpeg renders complete within timeout; no distributed rendering
7. **Colorspace compatibility**: All hex colors render identically across FFmpeg encoders (libx264 H.264)

---

**Document Version**: 1.0  
**Created**: October 2026  
**Status**: Ready for Design Phase
