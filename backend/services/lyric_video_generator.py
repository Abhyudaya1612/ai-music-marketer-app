"""Lyric video generation service with FFmpeg."""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Subtitle:
    start_ms: int
    end_ms: int
    text: str


class LyricVideoError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def parse_srt(text: str) -> list[Subtitle]:
    """Parse SRT subtitle format into list of Subtitle objects."""
    subtitles = []
    blocks = re.split(r"\n\s*\n", text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            # Line 1: index (ignored)
            # Line 2: timestamp
            timecode = lines[1]
            match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", timecode)
            if not match:
                continue

            start_h, start_m, start_s, start_ms, end_h, end_m, end_s, end_ms = map(int, match.groups())
            start_ms_total = start_h * 3600000 + start_m * 60000 + start_s * 1000 + start_ms
            end_ms_total = end_h * 3600000 + end_m * 60000 + end_s * 1000 + end_ms

            # Rest: text
            text = "\n".join(lines[2:]).strip()

            subtitles.append(Subtitle(start_ms=start_ms_total, end_ms=end_ms_total, text=text))
        except Exception as e:
            logger.warning(f"srt_parse_error: {e}")
            continue

    return subtitles


def parse_lrc(text: str) -> list[Subtitle]:
    """Parse LRC lyrics format into list of Subtitle objects."""
    subtitles = []
    lines = text.strip().split("\n")

    for line in lines:
        # LRC format: [MM:SS.MS]text
        match = re.match(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\](.+)", line)
        if not match:
            continue

        try:
            minutes, seconds, centis, text = match.groups()
            start_ms = int(minutes) * 60000 + int(seconds) * 1000 + (int(centis or 0) * 10)
            # Assume line duration is 3 seconds (typical)
            end_ms = start_ms + 3000

            subtitles.append(Subtitle(start_ms=start_ms, end_ms=end_ms, text=text.strip()))
        except Exception as e:
            logger.warning(f"lrc_parse_error: {e}")
            continue

    return subtitles


def build_ass_subtitles(timing_list: list[Subtitle]) -> str:
    """Build ASS format subtitle string for FFmpeg."""
    # ASS header
    ass = """[Script Info]
Title: Lyric Video
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,50,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for sub in timing_list:
        start_h = sub.start_ms // 3600000
        start_m = (sub.start_ms % 3600000) // 60000
        start_s = (sub.start_ms % 60000) // 1000
        start_cs = (sub.start_ms % 1000) // 10

        end_h = sub.end_ms // 3600000
        end_m = (sub.end_ms % 3600000) // 60000
        end_s = (sub.end_ms % 60000) // 1000
        end_cs = (sub.end_ms % 1000) // 10

        start_time = f"{start_h}:{start_m:02d}:{start_s:02d}.{start_cs:02d}"
        end_time = f"{end_h}:{end_m:02d}:{end_s:02d}.{end_cs:02d}"

        text = sub.text.replace("\n", "\\N")
        ass += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"

    return ass


def render_lyric_video(
    input_audio_path: str,
    lyrics_text: str | None,
    lyrics_format: str = "srt",
    output_path: str | None = None,
    mode: str = "waveform",
) -> dict:
    """
    Render a lyric video with optional subtitle overlay.
    
    Args:
        input_audio_path: Path to input audio file
        lyrics_text: Lyrics text in SRT or LRC format (optional)
        lyrics_format: "srt" or "lrc"
        output_path: Path to output MP4 file (optional, generated if not provided)
        mode: "waveform" or "spectrum"
    
    Returns:
        Dict with video_id, duration_seconds, output_path
        
    Raises:
        LyricVideoError on failure
    """
    if not shutil.which(settings.ffmpeg_path):
        raise LyricVideoError("FFMPEG_NOT_FOUND")
    if not shutil.which(settings.ffprobe_path):
        raise LyricVideoError("FFPROBE_NOT_FOUND")

    # Generate output path if not provided
    if output_path is None:
        output_path = str(Path(tempfile.gettempdir()) / "lyric_video_output.mp4")

    try:
        # Get input duration
        result = subprocess.run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1:noprint_filename=1",
                input_audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration_seconds = float(result.stdout.strip())
    except Exception as e:
        logger.error(f"ffprobe_error: {e}")
        raise LyricVideoError("AUDIO_DURATION_UNAVAILABLE")

    # Build FFmpeg filter chain
    if mode == "waveform":
        audio_filter = "showwaves=s=1280x720:colors=0xFFFFFF"
    elif mode == "spectrum":
        audio_filter = "showspectrum=s=1280x720:colors=cool"
    else:
        audio_filter = "showwaves=s=1280x720:colors=0xFFFFFF"

    # Create temporary ASS file if lyrics available
    ass_file = None
    if lyrics_text and lyrics_text.strip():
        try:
            if lyrics_format.lower() == "lrc":
                subtitles = parse_lrc(lyrics_text)
            else:
                subtitles = parse_srt(lyrics_text)

            if subtitles:
                ass_content = build_ass_subtitles(subtitles)
                ass_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False)
                ass_file.write(ass_content)
                ass_file.close()
                # Add subtitle overlay filter
                audio_filter += f",subtitles={ass_file.name}"
                logger.info("lyric_video_ass_created", extra={"subtitle_count": len(subtitles)})
            else:
                logger.warning("lyric_video_no_subtitles_parsed")
        except Exception as e:
            logger.warning(f"lyric_video_subtitle_error: {e}")

    # Build FFmpeg command
    cmd = [
        settings.ffmpeg_path,
        "-i",
        input_audio_path,
        "-filter_complex",
        audio_filter,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-y",  # Overwrite output
        output_path,
    ]

    try:
        start_time = time.monotonic()
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=settings.lyric_video_max_render_time_seconds,
        )
        elapsed = time.monotonic() - start_time

        logger.info(
            "lyric_video_generated",
            extra={
                "duration_seconds": duration_seconds,
                "output_path": output_path,
                "render_time_seconds": elapsed,
            },
        )

        return {
            "video_id": Path(output_path).stem,
            "duration_seconds": duration_seconds,
            "output_path": output_path,
        }

    except subprocess.TimeoutExpired:
        raise LyricVideoError("RENDER_TIMEOUT")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg_error: {e}")
        raise LyricVideoError("FFMPEG_RENDER_FAILED")
    except Exception as e:
        logger.error(f"lyric_video_render_error: {type(e).__name__}: {e}")
        raise LyricVideoError("RENDER_ERROR")
    finally:
        # Clean up temporary ASS file
        if ass_file:
            try:
                Path(ass_file.name).unlink()
            except Exception:
                pass
