"""Private, local FFmpeg motion-graphics rendering and output validation."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from .storage import render_output_path

logger = logging.getLogger(__name__)


class VideoRenderError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def renderer_capabilities() -> dict[str, bool]:
    # Check FFmpeg availability - simple path check
    ffmpeg_path = Path(settings.ffmpeg_path)
    ffmpeg_available = ffmpeg_path.exists() and ffmpeg_path.is_file()
    
    # Check FFprobe availability - simple path check
    ffprobe_path = Path(settings.ffprobe_path)
    ffprobe_available = ffprobe_path.exists() and ffprobe_path.is_file()
    
    if not ffmpeg_available or not ffprobe_available:
        logger.warning("renderer_capabilities_unavailable", extra={"reason": "ffmpeg or ffprobe not found"})
        return {
            "music_visualizer": False,
            "full_music_video": False,
        }
    font_path = _font_path()
    if font_path is None:
        logger.warning("renderer_capabilities_unavailable", extra={"reason": "required font not found"})
        return {
            "music_visualizer": False,
            "full_music_video": False,
        }
    try:
        filters = subprocess.run(
            [settings.ffmpeg_path, "-hide_banner", "-filters"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        ).stdout
        encoders = subprocess.run(
            [settings.ffmpeg_path, "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        logger.warning("renderer_capabilities_unavailable", extra={"reason": "ffmpeg query failed"})
        return {
            "music_visualizer": False,
            "full_music_video": False,
        }
    common = "drawtext" in filters and "libx264" in encoders and "aac" in encoders
    return {
        "music_visualizer": common and "showwaves" in filters,
        "full_music_video": common and "showspectrum" in filters,
    }


def build_scene_plan(duration_seconds: float, render_format: str) -> list[dict[str, Any]]:
    if duration_seconds <= 0:
        raise VideoRenderError("VIDEO_SOURCE_UNAVAILABLE")
    intro_end = min(6.0, duration_seconds / 4)
    outro_start = max(intro_end, duration_seconds - min(6.0, duration_seconds / 4))
    return [
        {
            "name": "opening_title",
            "start_seconds": 0.0,
            "end_seconds": round(intro_end, 3),
            "transition": "fade",
        },
        {
            "name": "audio_reactive",
            "start_seconds": round(intro_end, 3),
            "end_seconds": round(outro_start, 3),
            "transition": "cut",
        },
        {
            "name": "closing_card",
            "start_seconds": round(outro_start, 3),
            "end_seconds": round(duration_seconds, 3),
            "transition": "fade",
        },
    ]


def _font_path() -> Path | None:
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _filter_escape_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return value.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


def _filter_time(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _scene_alpha(scene: dict[str, Any]) -> str:
    start = _filter_time(scene["start_seconds"])
    end = _filter_time(scene["end_seconds"])
    duration = max(0.2, min(0.8, (scene["end_seconds"] - scene["start_seconds"]) / 2))
    transition = _filter_time(duration)
    return (
        f"if(between(t\\,{start}\\,{end})\\,"
        f"max(0\\,min(min(1\\,(t-{start})/{transition})\\,({end}-t)/{transition}))\\,0)"
    )


def _single_line(value: str | None, fallback: str) -> str:
    cleaned = " ".join((value or "").replace("\x00", " ").split())
    return cleaned[:255] or fallback


def _video_filter(
    render_format: str,
    scenes: list[dict[str, Any]],
    font_path: Path,
) -> str:
    if render_format == "music_visualizer":
        visualizer = (
            "showwaves=s=1280x720:mode=line:rate=30:"
            "colors=0xd7fb58:scale=sqrt"
        )
    else:
        visualizer = (
            "showspectrum=s=1280x720:mode=combined:color=rainbow:"
            "scale=log:fps=30"
        )
    font = _filter_escape_path(font_path)
    font_size = 58 if render_format == "full_music_video" else 52
    base_filter = (
        f"[0:a]{visualizer},format=yuv420p,"
        "fade=t=in:st=0:d=0.6,"
        f"fade=t=out:st={_filter_time(max(0, scenes[-1]['end_seconds'] - 0.6))}:d=0.6"
        "[base]"
    )
    overlays = ",".join(
        (
            f"drawtext=fontfile='{font}':textfile=title.txt:expansion=none:"
            f"fontcolor=white:fontsize={font_size}:x=(w-text_w)/2:y=h*0.34:"
            f"box=1:boxcolor=0x101214@0.55:boxborderw=24:alpha='{_scene_alpha(scenes[0])}'",
            (
                f"drawtext=fontfile='{font}':textfile=artist.txt:expansion=none:"
                f"fontcolor=0xd7fb58:fontsize=30:x=(w-text_w)/2:y=h*0.46:"
                f"box=1:boxcolor=0x101214@0.45:boxborderw=18:alpha='{_scene_alpha(scenes[0])}'"
            ),
            (
                f"drawtext=fontfile='{font}':textfile=closing.txt:expansion=none:"
                f"fontcolor=white:fontsize=42:x=(w-text_w)/2:y=h*0.78:"
                f"box=1:boxcolor=0x101214@0.55:boxborderw=20:alpha='{_scene_alpha(scenes[2])}'"
            ),
        )
    )
    return f"{base_filter};[base]{overlays}[v]"


def _probe_output(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,codec_name,width,height,duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        probe = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise VideoRenderError("VIDEO_OUTPUT_INVALID") from exc
    streams = probe.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    format_data = probe.get("format", {})
    try:
        duration = float(format_data["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VideoRenderError("VIDEO_OUTPUT_INVALID") from exc
    if (
        video is None
        or audio is None
        or video.get("codec_name") != "h264"
        or audio.get("codec_name") != "aac"
        or video.get("width") != 1280
        or video.get("height") != 720
        or "mp4" not in format_data.get("format_name", "")
        or duration <= 0
    ):
        raise VideoRenderError("VIDEO_OUTPUT_INVALID")
    return {
        "container": "mp4",
        "video_codec": video["codec_name"],
        "audio_codec": audio["codec_name"],
        "width": video["width"],
        "height": video["height"],
        "aspect_ratio": "16:9",
        "duration_seconds": round(duration, 3),
        "audio_present": True,
    }


def _ffmpeg_version() -> str:
    try:
        result = subprocess.run(
            [settings.ffmpeg_path, "-version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VideoRenderError("VIDEO_RENDERER_UNAVAILABLE") from exc
    return result.stdout.splitlines()[0][:160] if result.stdout else "unknown"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_motion_graphics(
    source_path: Path,
    render_id: str,
    render_format: str,
    title: str,
    artist_name: str | None,
    duration_seconds: float,
    progress_callback: Callable[[int], None],
) -> dict[str, Any]:
    _render_start = time.monotonic()
    logger.info("render_started", extra={
        "render_id": render_id,
        "render_format": render_format,
        "duration_seconds": duration_seconds,
    })
    supported = renderer_capabilities()
    if not supported.get(render_format, False):
        raise VideoRenderError("VIDEO_RENDERER_UNAVAILABLE")
    if not source_path.is_file():
        raise VideoRenderError("VIDEO_SOURCE_UNAVAILABLE")

    renderer_version = _ffmpeg_version()
    scenes = build_scene_plan(duration_seconds, render_format)
    output_path = render_output_path(render_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path = output_path.parent / "ffmpeg-progress.txt"
    font_path = _font_path()
    if font_path is None:
        raise VideoRenderError("VIDEO_RENDERER_UNAVAILABLE")
    files = {
        "title.txt": _single_line(title, "Untitled track"),
        "artist.txt": _single_line(artist_name, "Independent artist"),
        "closing.txt": _single_line(title, "Untitled track"),
    }
    for name, text in files.items():
        (output_path.parent / name).write_text(text, encoding="utf-8")

    filter_graph = _video_filter(render_format, scenes, font_path)
    timeout_seconds = min(7200, max(300, int(duration_seconds * 10)))
    command = [
        settings.ffmpeg_path,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(source_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "0:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        "-progress",
        str(progress_path),
        "-nostats",
        str(output_path),
    ]
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    last_percent = 10
    try:
        progress_callback(10)
        process = subprocess.Popen(
            command,
            cwd=output_path.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        while process.poll() is None:
            if time.monotonic() - started > timeout_seconds:
                process.kill()
                process.wait()
                raise VideoRenderError("VIDEO_RENDER_TIMEOUT")
            if progress_path.is_file():
                progress_values: dict[str, str] = {}
                for line in progress_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        progress_values[key] = value
                try:
                    elapsed = int(progress_values.get("out_time_ms", "0")) / 1_000_000
                    percent = min(90, 10 + int(80 * elapsed / duration_seconds))
                except (ValueError, ZeroDivisionError):
                    percent = last_percent
                if percent > last_percent:
                    progress_callback(percent)
                    last_percent = percent
            time.sleep(0.25)
        if process.returncode != 0:
            raise VideoRenderError("VIDEO_RENDER_FAILED")
        progress_callback(92)
        metadata = _probe_output(output_path)
        if abs(metadata["duration_seconds"] - duration_seconds) > 1.0:
            raise VideoRenderError("VIDEO_OUTPUT_INVALID")
        checksum = _file_sha256(output_path)
        result = {
            "metadata": metadata,
            "size_bytes": output_path.stat().st_size,
            "checksum_sha256": checksum,
            "scene_plan": scenes,
            "render_settings": {
                "renderer": "local_ffmpeg_motion_graphics",
                "renderer_version": renderer_version,
                "render_format": render_format,
                "resolution": "1280x720",
                "frame_rate": 30,
                "video_codec": "h264",
                "audio_codec": "aac",
                "preset": "veryfast",
                "crf": 23,
                "uses_uploaded_artwork": False,
                "uses_ai_generated_footage": False,
            },
            "provenance": {
                "source_kind": "owner-authorized-original-audio",
                "source_sha256": None,
                "visual_generation": "deterministic local FFmpeg waveform or spectrum graphics",
                "model": None,
                "artwork": "not used",
                "publishing": "not performed",
            },
        }
        logger.info("render_completed", extra={
            "render_id": render_id,
            "duration_ms": round((time.monotonic() - _render_start) * 1000),
            "size_bytes": result["size_bytes"],
        })
        return result
    except (OSError, subprocess.SubprocessError) as exc:
        raise VideoRenderError("VIDEO_RENDERER_UNAVAILABLE") from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        progress_path.unlink(missing_ok=True)
        for name in files:
            (output_path.parent / name).unlink(missing_ok=True)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
