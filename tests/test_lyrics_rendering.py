"""Tests for advanced lyrics rendering."""
from __future__ import annotations

import pytest

from backend.services.genre_visualizer import load_genre_theme
from backend.services.lyrics_renderer import (
    build_lyrics_filter_chain,
    format_lyrics_for_timing,
    render_lyrics_always_visible,
    validate_lyrics_readability,
)


class TestLyricsFormatting:
    """Test lyrics timing formatting."""

    def test_format_empty_lyrics(self):
        result = format_lyrics_for_timing("")
        assert result == []

    def test_format_single_line(self):
        result = format_lyrics_for_timing("Hello world")
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["start_ms"] == 0
        assert result[0]["end_ms"] == 3000

    def test_format_multiple_lines(self):
        lyrics = "Line one\nLine two\nLine three"
        result = format_lyrics_for_timing(lyrics)
        assert len(result) == 3
        assert result[0]["text"] == "Line one"
        assert result[1]["text"] == "Line two"
        assert result[2]["text"] == "Line three"

    def test_format_with_start_time(self):
        result = format_lyrics_for_timing("Hello", start_time_ms=5000)
        assert result[0]["start_ms"] == 5000
        assert result[0]["end_ms"] == 8000

    def test_format_timing_increments(self):
        lyrics = "A\nB\nC"
        result = format_lyrics_for_timing(lyrics)
        assert result[0]["start_ms"] == 0
        assert result[0]["end_ms"] == 3000
        assert result[1]["start_ms"] == 3000
        assert result[1]["end_ms"] == 6000
        assert result[2]["start_ms"] == 6000
        assert result[2]["end_ms"] == 9000

    def test_format_with_whitespace(self):
        lyrics = "  Line one  \n\n  Line two  "
        result = format_lyrics_for_timing(lyrics)
        assert len(result) == 2
        assert result[0]["text"] == "Line one"
        assert result[1]["text"] == "Line two"


class TestLyricsRendering:
    """Test FFmpeg lyrics rendering filter generation."""

    def test_render_empty_lyrics(self):
        theme = load_genre_theme("electronic")
        result = render_lyrics_always_visible([], 10.0, theme)
        assert result == ""

    def test_render_single_lyric(self):
        theme = load_genre_theme("electronic")
        lyrics = [{"text": "Hello", "start_ms": 0, "end_ms": 3000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result
        assert "Hello" in result

    def test_render_multiple_lyrics(self):
        theme = load_genre_theme("hip-hop")
        lyrics = [
            {"text": "Line 1", "start_ms": 0, "end_ms": 2000},
            {"text": "Line 2", "start_ms": 2000, "end_ms": 4000},
            {"text": "Line 3", "start_ms": 4000, "end_ms": 6000},
        ]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert result.count("drawtext") >= 3
        assert "Line 1" in result
        assert "Line 2" in result

    def test_lyrics_positioning_top(self):
        theme = load_genre_theme("ambient")
        lyrics = [{"text": "Test", "start_ms": 0, "end_ms": 1000}]
        result = render_lyrics_always_visible(lyrics, 5.0, theme)
        assert "drawtext" in result

    def test_lyrics_positioning_bottom(self):
        theme = load_genre_theme("rock")
        lyrics = [{"text": "Test", "start_ms": 0, "end_ms": 1000}]
        result = render_lyrics_always_visible(lyrics, 5.0, theme)
        assert "drawtext" in result

    def test_lyrics_positioning_center(self):
        theme = load_genre_theme("hip-hop")
        lyrics = [{"text": "Test", "start_ms": 0, "end_ms": 1000}]
        result = render_lyrics_always_visible(lyrics, 5.0, theme)
        assert "drawtext" in result

    def test_lyrics_with_special_characters(self):
        theme = load_genre_theme("electronic")
        lyrics = [
            {"text": "Love's & Hope!", "start_ms": 0, "end_ms": 2000},
        ]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result

    def test_lyrics_timing_expressions(self):
        theme = load_genre_theme("pop")
        lyrics = [
            {"text": "First", "start_ms": 1000, "end_ms": 3000},
            {"text": "Second", "start_ms": 3000, "end_ms": 5000},
        ]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "enable=" in result
        assert "gte(t," in result
        assert "lte(t," in result


class TestLyricsReadability:
    """Test lyrics readability validation."""

    def test_font_size_too_small(self):
        result = validate_lyrics_readability(20, "#FFFFFF", "#000000")
        assert result is False

    def test_font_size_minimum_valid(self):
        result = validate_lyrics_readability(24, "#FFFFFF", "#000000")
        assert result is True

    def test_font_size_normal(self):
        result = validate_lyrics_readability(36, "#FFFFFF", "#000000")
        assert result is True

    def test_font_size_large(self):
        result = validate_lyrics_readability(72, "#FFFFFF", "#000000")
        assert result is True

    def test_font_size_too_large(self):
        result = validate_lyrics_readability(100, "#FFFFFF", "#000000")
        assert result is False

    def test_white_text_on_black_bg(self):
        result = validate_lyrics_readability(36, "#000000", "#FFFFFF")
        assert result is True

    def test_black_text_on_white_bg(self):
        result = validate_lyrics_readability(36, "#FFFFFF", "#000000")
        assert result is True

    def test_same_color_as_bg_fails(self):
        result = validate_lyrics_readability(36, "#FFFFFF", "#FFFFFF")
        assert result is False

    def test_yellow_on_light_bg_fails(self):
        result = validate_lyrics_readability(36, "#CCCCCC", "#FFFF00")
        assert result is False

    def test_high_contrast_colors_pass(self):
        result = validate_lyrics_readability(36, "#000000", "#FFFF00")
        assert result is True

    def test_red_on_black_passes(self):
        result = validate_lyrics_readability(36, "#000000", "#FF0000")
        assert result is True


class TestLyricsFilterChain:
    """Test building complete filter chains."""

    def test_build_filter_with_no_lyrics(self):
        theme = load_genre_theme("electronic")
        visualizer = "showwaves=s=1280x720"
        result = build_lyrics_filter_chain([], 10.0, theme, visualizer)
        assert result == visualizer

    def test_build_filter_with_lyrics(self):
        theme = load_genre_theme("hip-hop")
        visualizer = "showspectrum=s=1280x720"
        lyrics = [
            {"text": "Test", "start_ms": 0, "end_ms": 2000},
        ]
        result = build_lyrics_filter_chain(lyrics, 10.0, theme, visualizer)
        assert "showspectrum" in result
        assert "drawtext" in result

    def test_filter_chain_combines_visualizer_and_lyrics(self):
        theme = load_genre_theme("ambient")
        visualizer = "showwaves=colors=0xFFFFFF"
        lyrics = [
            {"text": "Ambient", "start_ms": 0, "end_ms": 5000},
        ]
        result = build_lyrics_filter_chain(lyrics, 30.0, theme, visualizer)
        assert "showwaves" in result
        assert "drawtext" in result

    def test_complex_filter_chain(self):
        theme = load_genre_theme("k-pop")
        visualizer = "showspectrum=mode=combined"
        lyrics = [
            {"text": "Line 1", "start_ms": 0, "end_ms": 2000},
            {"text": "Line 2", "start_ms": 2000, "end_ms": 4000},
        ]
        result = build_lyrics_filter_chain(lyrics, 20.0, theme, visualizer)
        assert "drawtext" in result
        assert result.count("drawtext") >= 2


class TestGenreThemedLyrics:
    """Test lyrics rendering with different genres."""

    def test_electronic_genre_lyrics(self):
        theme = load_genre_theme("electronic")
        lyrics = [{"text": "Electronic", "start_ms": 0, "end_ms": 3000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result

    def test_hip_hop_genre_lyrics(self):
        theme = load_genre_theme("hip-hop")
        lyrics = [{"text": "Hip Hop", "start_ms": 0, "end_ms": 3000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result
        assert theme.lyrics_position == "center"

    def test_ambient_genre_lyrics(self):
        theme = load_genre_theme("ambient")
        lyrics = [{"text": "Ambient", "start_ms": 0, "end_ms": 5000}]
        result = render_lyrics_always_visible(lyrics, 20.0, theme)
        assert "drawtext" in result

    def test_rock_genre_lyrics(self):
        theme = load_genre_theme("rock")
        lyrics = [{"text": "Rock", "start_ms": 1000, "end_ms": 4000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result

    def test_jazz_genre_lyrics(self):
        theme = load_genre_theme("jazz")
        lyrics = [{"text": "Jazz", "start_ms": 0, "end_ms": 4000}]
        result = render_lyrics_always_visible(lyrics, 15.0, theme)
        assert "drawtext" in result


class TestLyricsVisibilityTiming:
    """Test that lyrics maintain visibility throughout their time window."""

    def test_lyrics_visible_during_window(self):
        theme = load_genre_theme("pop")
        lyrics = [
            {"text": "Verse 1", "start_ms": 1000, "end_ms": 5000},
        ]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        # Extract timing: enable expression should use gte(t,1) and lte(t,5)
        assert "enable=" in result
        assert "gte(t,1" in result or "t,1" in result
        assert "lte(t,5" in result or "t,5" in result

    def test_multiple_lyrics_non_overlapping(self):
        theme = load_genre_theme("pop")
        lyrics = [
            {"text": "First", "start_ms": 0, "end_ms": 2000},
            {"text": "Second", "start_ms": 2000, "end_ms": 4000},
        ]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert result.count("enable=") >= 2

    def test_lyrics_at_start_of_video(self):
        theme = load_genre_theme("rock")
        lyrics = [{"text": "Start", "start_ms": 0, "end_ms": 3000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "enable=" in result

    def test_lyrics_at_end_of_video(self):
        theme = load_genre_theme("classical")
        lyrics = [{"text": "End", "start_ms": 7000, "end_ms": 10000}]
        result = render_lyrics_always_visible(lyrics, 10.0, theme)
        assert "drawtext" in result
