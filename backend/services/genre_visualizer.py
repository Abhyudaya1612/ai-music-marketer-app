"""Genre-based visualization theming for lyric videos."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GenreVisualizerError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class GenreThemeConfig:
    """Configuration for genre-specific visualizer theme."""
    
    def __init__(
        self,
        genre: str,
        visualizer_type: str,
        colors: list[str],
        lyrics_position: str,
        lyrics_font_family: str,
        lyrics_font_size: int,
        tempo_sync: bool,
        background_color: str,
    ):
        self.genre = genre
        self.visualizer_type = visualizer_type
        self.colors = colors
        self.lyrics_position = lyrics_position
        self.lyrics_font_family = lyrics_font_family
        self.lyrics_font_size = lyrics_font_size
        self.tempo_sync = tempo_sync
        self.background_color = background_color
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "genre": self.genre,
            "visualizer_type": self.visualizer_type,
            "colors": self.colors,
            "lyrics_position": self.lyrics_position,
            "lyrics_font_family": self.lyrics_font_family,
            "lyrics_font_size": self.lyrics_font_size,
            "tempo_sync": self.tempo_sync,
            "background_color": self.background_color,
        }


def _load_genre_themes() -> dict[str, dict[str, Any]]:
    """Load genre themes from JSON file."""
    try:
        data_dir = Path(__file__).parent.parent / "data"
        themes_path = data_dir / "genre_themes.json"
        with open(themes_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("failed_to_load_genre_themes", extra={"error": str(exc)})
        raise GenreVisualizerError("GENRE_THEMES_UNAVAILABLE") from exc


_GENRE_CACHE: dict[str, dict[str, Any]] | None = None


def _get_genre_cache() -> dict[str, dict[str, Any]]:
    """Get or initialize genre themes cache."""
    global _GENRE_CACHE
    if _GENRE_CACHE is None:
        _GENRE_CACHE = _load_genre_themes()
    return _GENRE_CACHE


def load_genre_theme(genre: str | None) -> GenreThemeConfig:
    """Load theme configuration for a given genre.
    
    Args:
        genre: Genre name (lowercase, hyphen-separated)
    
    Returns:
        GenreThemeConfig with theme settings
    
    Raises:
        GenreVisualizerError if genre not found
    """
    if not genre:
        genre = "electronic"
    
    genre_lower = genre.lower().strip()
    themes = _get_genre_cache()
    
    if genre_lower not in themes:
        logger.warning("genre_not_found", extra={"genre": genre_lower, "fallback": "electronic"})
        genre_lower = "electronic"
    
    config = themes[genre_lower]
    return GenreThemeConfig(
        genre=genre_lower,
        visualizer_type=config.get("visualizer_type", "waveform"),
        colors=config.get("colors", ["#FFFFFF"]),
        lyrics_position=config.get("lyrics_position", "bottom"),
        lyrics_font_family=config.get("lyrics_font_family", "Arial"),
        lyrics_font_size=config.get("lyrics_font_size", 36),
        tempo_sync=config.get("tempo_sync", False),
        background_color=config.get("background_color", "#000000"),
    )


def get_all_genres() -> list[str]:
    """Get list of all supported genres."""
    themes = _get_genre_cache()
    return sorted(list(themes.keys()))


def get_genre_with_config(genre: str | None) -> dict[str, Any]:
    """Get genre with its full configuration."""
    theme = load_genre_theme(genre)
    return theme.to_dict()


def detect_genre_from_metadata(
    song_metadata: dict[str, Any],
    song_title: str | None = None,
    artist_name: str | None = None,
    genre_preferences: list[str] | None = None,
) -> str:
    """Infer genre from metadata.
    
    Priority:
    1. genre_preferences list (first preference)
    2. Audio features analysis (if available)
    3. Default to 'electronic'
    
    Args:
        song_metadata: Dictionary with song metadata/features
        song_title: Song title (unused, for future expansion)
        artist_name: Artist name (unused, for future expansion)
        genre_preferences: List of genre preferences from user
    
    Returns:
        Genre string (lowercase)
    """
    # First priority: user-provided genre preferences
    if genre_preferences and len(genre_preferences) > 0:
        preferred = genre_preferences[0].lower().strip()
        themes = _get_genre_cache()
        if preferred in themes:
            return preferred
    
    # Second priority: audio feature analysis
    features = song_metadata.get("audio_features", {})
    if features:
        energy = features.get("energy", {}).get("value", 0.5)
        danceability = features.get("danceability", {}).get("value", 0.5)
        acousticness = features.get("acousticness", {}).get("value", 0.5)
        
        # Simple heuristics based on audio features
        if acousticness > 0.7:
            return "acoustic"
        if danceability > 0.75:
            return "electronic"
        if energy > 0.8:
            return "metal"
        if energy < 0.3:
            return "ambient"
        if danceability > 0.6:
            return "house"
    
    # Default fallback
    return "electronic"


def get_ffmpeg_filters(theme: GenreThemeConfig, duration: float) -> str:
    """Build FFmpeg filter chain for visualizer.
    
    Args:
        theme: GenreThemeConfig with visualizer settings
        duration: Duration of audio in seconds
    
    Returns:
        FFmpeg filter string for -filter_complex
    """
    visualizer_type = theme.visualizer_type
    colors = theme.colors
    
    # Build primary color string (first color)
    primary_color = colors[0] if colors else "#FFFFFF"
    
    # Remove leading # if present
    if primary_color.startswith("#"):
        primary_color = primary_color[1:]
    
    # Convert hex to FFmpeg color format (0xRRGGBB)
    try:
        ffmpeg_color = f"0x{primary_color}"
    except Exception:
        ffmpeg_color = "0xFFFFFF"
    
    if visualizer_type == "spectrum":
        # Spectrum analyzer
        filter_str = (
            f"showspectrum=s=1280x720:mode=combined:color=rainbow:"
            f"scale=log:fps=30"
        )
    else:
        # Default to waveform
        filter_str = (
            f"showwaves=s=1280x720:mode=line:rate=30:"
            f"colors={ffmpeg_color}:scale=sqrt"
        )
    
    return filter_str


def validate_theme_contrast(
    text_color: str,
    background_color: str,
) -> bool:
    """Validate that text color contrasts sufficiently with background.
    
    Args:
        text_color: Text color in #RRGGBB format
        background_color: Background color in #RRGGBB format
    
    Returns:
        True if contrast is sufficient for readability
    """
    def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """Convert #RRGGBB to (R, G, B)."""
        hex_str = hex_color.lstrip("#")
        if len(hex_str) != 6:
            return (255, 255, 255)
        try:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))  # type: ignore
        except ValueError:
            return (255, 255, 255)
    
    def relative_luminance(rgb: tuple[int, int, int]) -> float:
        """Calculate relative luminance per WCAG."""
        r, g, b = rgb
        r_norm = r / 255.0
        g_norm = g / 255.0
        b_norm = b / 255.0
        
        r_lin = r_norm / 12.92 if r_norm <= 0.03928 else ((r_norm + 0.055) / 1.055) ** 2.4
        g_lin = g_norm / 12.92 if g_norm <= 0.03928 else ((g_norm + 0.055) / 1.055) ** 2.4
        b_lin = b_norm / 12.92 if b_norm <= 0.03928 else ((b_norm + 0.055) / 1.055) ** 2.4
        
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
    
    text_rgb = hex_to_rgb(text_color)
    bg_rgb = hex_to_rgb(background_color)
    
    text_lum = relative_luminance(text_rgb)
    bg_lum = relative_luminance(bg_rgb)
    
    # Calculate contrast ratio
    lighter = max(text_lum, bg_lum)
    darker = min(text_lum, bg_lum)
    contrast_ratio = (lighter + 0.05) / (darker + 0.05)
    
    # WCAG AA requires 4.5:1 for normal text
    return contrast_ratio >= 4.5
