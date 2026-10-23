"""Advanced lyrics rendering with genre-aware styling and always-visible display."""
from __future__ import annotations

import logging
from typing import Any

from .genre_visualizer import GenreThemeConfig

logger = logging.getLogger(__name__)


class LyricsRendererError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def render_lyrics_always_visible(
    lyrics: list[dict[str, Any]],
    duration: float,
    theme: GenreThemeConfig,
) -> str:
    """Generate FFmpeg drawtext command for lyrics that are always visible.
    
    Lyrics are rendered throughout the entire video duration with proper
    timing synchronization, genre-aware positioning and styling.
    
    Args:
        lyrics: List of {"text": "...", "start_ms": 0, "end_ms": 1000}
        duration: Duration of audio in seconds
        theme: GenreThemeConfig with styling settings
    
    Returns:
        FFmpeg filter string for drawtext with proper timing and styling
    """
    if not lyrics or duration <= 0:
        return ""
    
    # Determine text color based on genre theme
    # Use white for dark backgrounds, darker text for light backgrounds
    bg_color = theme.background_color.lstrip("#")
    
    # Simple brightness calculation
    try:
        r = int(bg_color[0:2], 16)
        g = int(bg_color[2:4], 16)
        b = int(bg_color[4:6], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = "FFFFFF" if brightness < 128 else "000000"
    except (ValueError, IndexError):
        text_color = "FFFFFF"
    
    filters = []
    
    # Position mapping
    position_map = {
        "top": "y=h*0.15",
        "bottom": "y=h*0.85",
        "center": "y=h*0.5",
        "flowing": "y=h/2-(text_h/2)",  # Dynamically centered
    }
    
    y_pos = position_map.get(theme.lyrics_position, "y=h*0.85")
    
    # Font size from theme
    font_size = theme.lyrics_font_size
    font_family = theme.lyrics_font_family
    
    # Build FFmpeg drawtext filters for each lyric
    for idx, lyric in enumerate(lyrics):
        text = lyric.get("text", "").replace("'", "\\'").replace('"', '\\"')
        start_ms = lyric.get("start_ms", 0)
        end_ms = lyric.get("end_ms", 0)
        
        if not text:
            continue
        
        # Convert milliseconds to seconds
        start_sec = start_ms / 1000.0
        end_sec = end_ms / 1000.0
        
        # Build enable expression for timing
        # Ensure lyrics are visible during their time window
        enable_expr = f"gte(t,{start_sec})*lte(t,{end_sec})"
        
        # Build drawtext filter
        drawtext = (
            f"drawtext="
            f"text='{text}':"
            f"fontfile='Arial':"
            f"fontsize={font_size}:"
            f"fontcolor=0x{text_color}:"
            f"borderw=2:"
            f"bordercolor=0x000000:"
            f"boxcolor=0x00000099:"
            f"boxborderw=10:"
            f"{y_pos}:"
            f"x=(w-text_w)/2:"
            f"enable='{enable_expr}'"
        )
        
        filters.append(drawtext)
    
    # Combine all drawtext filters
    return ",".join(filters) if filters else ""


def validate_lyrics_readability(
    font_size: int,
    bg_color: str,
    text_color: str,
) -> bool:
    """Ensure sufficient contrast for lyrics readability.
    
    Args:
        font_size: Font size in pixels
        bg_color: Background color in #RRGGBB format
        text_color: Text color in #RRGGBB format
    
    Returns:
        True if contrast and size are sufficient for readability
    """
    # Minimum font size for video readability
    if font_size < 24:
        logger.warning("font_size_too_small", extra={"size": font_size})
        return False
    
    # Maximum font size
    if font_size > 96:
        logger.warning("font_size_too_large", extra={"size": font_size})
        return False
    
    # Validate contrast
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
    bg_rgb = hex_to_rgb(bg_color)
    
    text_lum = relative_luminance(text_rgb)
    bg_lum = relative_luminance(bg_rgb)
    
    # Calculate contrast ratio (WCAG standard)
    lighter = max(text_lum, bg_lum)
    darker = min(text_lum, bg_lum)
    contrast_ratio = (lighter + 0.05) / (darker + 0.05)
    
    # Require 4.5:1 for normal text, 3:1 minimum for large text
    min_ratio = 3.0 if font_size >= 24 else 4.5
    
    if contrast_ratio < min_ratio:
        logger.warning(
            "insufficient_contrast",
            extra={
                "contrast_ratio": contrast_ratio,
                "required": min_ratio,
            }
        )
        return False
    
    return True


def build_lyrics_filter_chain(
    lyrics: list[dict[str, Any]],
    duration: float,
    theme: GenreThemeConfig,
    visualizer_filter: str,
) -> str:
    """Build complete FFmpeg filter chain including visualizer and lyrics.
    
    Args:
        lyrics: List of lyric timing objects
        duration: Duration in seconds
        theme: Genre theme configuration
        visualizer_filter: Base visualizer filter string
    
    Returns:
        Complete FFmpeg filter_complex string
    """
    lyrics_filter = render_lyrics_always_visible(lyrics, duration, theme)
    
    if not lyrics_filter:
        return visualizer_filter
    
    # Combine visualizer with lyrics overlay
    return f"{visualizer_filter},{lyrics_filter}"


def format_lyrics_for_timing(
    raw_lyrics: str,
    start_time_ms: int = 0,
    end_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Format raw lyrics text into timed lyric objects.
    
    Args:
        raw_lyrics: Raw lyrics text (one line per lyric)
        start_time_ms: Start time in milliseconds
        end_time_ms: Optional end time; if not provided, calculates from line duration
    
    Returns:
        List of {"text": "...", "start_ms": ..., "end_ms": ...}
    """
    if not raw_lyrics:
        return []
    
    lines = [line.strip() for line in raw_lyrics.splitlines() if line.strip()]
    
    # If no end time specified, estimate based on typical timing
    line_duration_ms = 3000  # 3 seconds per line by default
    
    formatted = []
    current_time = start_time_ms
    
    for line in lines:
        end_ms = current_time + line_duration_ms
        formatted.append({
            "text": line,
            "start_ms": current_time,
            "end_ms": end_ms,
        })
        current_time = end_ms
    
    return formatted
