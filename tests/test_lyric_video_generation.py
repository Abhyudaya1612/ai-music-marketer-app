"""Tests for lyric video generation."""
import pytest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.services.lyric_video_generator import (
    parse_srt,
    parse_lrc,
    build_ass_subtitles,
    Subtitle,
    LyricVideoError,
)


class TestSRTParsing:
    """Test SRT subtitle parsing."""

    def test_parse_srt_basic(self):
        """Test basic SRT parsing."""
        srt_text = """1
00:00:01,000 --> 00:00:03,000
First line

2
00:00:04,000 --> 00:00:06,000
Second line"""

        result = parse_srt(srt_text)

        assert len(result) == 2
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 3000
        assert result[0].text == "First line"
        assert result[1].start_ms == 4000
        assert result[1].text == "Second line"

    def test_parse_srt_multiline_text(self):
        """Test SRT with multi-line subtitle text."""
        srt_text = """1
00:00:01,000 --> 00:00:03,000
Line one
Line two"""

        result = parse_srt(srt_text)

        assert len(result) == 1
        assert result[0].text == "Line one\nLine two"

    def test_parse_srt_empty(self):
        """Test empty SRT."""
        result = parse_srt("")
        assert len(result) == 0

    def test_parse_srt_malformed(self):
        """Test that malformed SRT entries are skipped."""
        srt_text = """1
invalid timestamp
This won't parse

2
00:00:01,000 --> 00:00:03,000
Valid entry"""

        result = parse_srt(srt_text)

        # Should only parse the valid entry
        assert len(result) == 1
        assert result[0].text == "Valid entry"


class TestLRCParsing:
    """Test LRC lyrics parsing."""

    def test_parse_lrc_basic(self):
        """Test basic LRC parsing."""
        lrc_text = """[00:10]First line
[00:15.50]Second line
[01:05]Third line"""

        result = parse_lrc(lrc_text)

        assert len(result) == 3
        assert result[0].start_ms == 10000
        assert result[0].text == "First line"
        assert result[1].start_ms == 15500
        assert result[1].text == "Second line"
        assert result[2].start_ms == 65000
        assert result[2].text == "Third line"

    def test_parse_lrc_with_minutes(self):
        """Test LRC with minutes and seconds."""
        lrc_text = "[01:30.75]Time at 1:30"

        result = parse_lrc(lrc_text)

        assert len(result) == 1
        # 1 minute 30.75 seconds = 90750 ms
        assert result[0].start_ms == 90750

    def test_parse_lrc_empty(self):
        """Test empty LRC."""
        result = parse_lrc("")
        assert len(result) == 0

    def test_parse_lrc_malformed(self):
        """Test that malformed LRC lines are skipped."""
        lrc_text = """[invalid]Not valid
[00:10]Valid line
Completely invalid
[00:20]Another valid"""

        result = parse_lrc(lrc_text)

        assert len(result) == 2
        assert result[0].text == "Valid line"
        assert result[1].text == "Another valid"


class TestASSSubtitles:
    """Test ASS subtitle format generation."""

    def test_build_ass_basic(self):
        """Test ASS subtitle generation."""
        subtitles = [
            Subtitle(start_ms=1000, end_ms=3000, text="First"),
            Subtitle(start_ms=4000, end_ms=6000, text="Second"),
        ]

        ass = build_ass_subtitles(subtitles)

        assert "[Script Info]" in ass
        assert "[V4+ Styles]" in ass
        assert "[Events]" in ass
        assert "First" in ass
        assert "Second" in ass

    def test_build_ass_timing_format(self):
        """Test that ASS timing format is correct."""
        subtitles = [
            Subtitle(start_ms=3661000, end_ms=3663000, text="Test"),  # 1:01:01 to 1:01:03
        ]

        ass = build_ass_subtitles(subtitles)

        assert "1:01:01" in ass
        assert "1:01:03" in ass

    def test_build_ass_multiline_text(self):
        """Test ASS with multi-line subtitle text."""
        subtitles = [
            Subtitle(start_ms=1000, end_ms=3000, text="Line 1\nLine 2"),
        ]

        ass = build_ass_subtitles(subtitles)

        # In ASS, newlines are represented as \\N
        assert "\\N" in ass

    def test_build_ass_empty(self):
        """Test ASS generation with no subtitles."""
        ass = build_ass_subtitles([])

        assert "[Script Info]" in ass
        assert "[Events]" in ass


class TestLyricVideoRendering:
    """Test lyric video rendering (requires FFmpeg)."""

    @pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="FFmpeg not available",
    )
    def test_render_without_lyrics(self):
        """Test rendering video without lyrics."""
        pytest.skip("Requires audio file and FFmpeg setup")

    @pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="FFmpeg not available",
    )
    def test_render_error_handling(self):
        """Test error handling when input file is missing."""
        from backend.services.lyric_video_generator import render_lyric_video

        with pytest.raises(LyricVideoError):
            render_lyric_video(
                input_audio_path="/nonexistent/audio.mp3",
                lyrics_text=None,
                output_path="/tmp/output.mp4",
            )

    @pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="FFmpeg not available",
    )
    def test_render_fallback_without_subtitles(self):
        """Test rendering without subtitle generation."""
        from backend.services.lyric_video_generator import render_lyric_video

        # This should gracefully degrade if subtitle parsing fails
        # (in a real test, would use a mock audio file)
        pytest.skip("Requires valid audio file")
