from __future__ import annotations

import subprocess
import uuid

import pytest

from backend.config import settings
from backend.services.storage import render_output_path
from backend.services.video_rendering import render_motion_graphics, renderer_capabilities


@pytest.mark.parametrize("render_format", ["music_visualizer", "full_music_video"])
def test_ffmpeg_renders_valid_private_mp4(tmp_path, monkeypatch, render_format):
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "private-media"))
    capabilities = renderer_capabilities()
    if not capabilities[render_format]:
        pytest.skip("Local FFmpeg renderer dependencies are unavailable.")

    source = tmp_path / "source.wav"
    subprocess.run(
        [
            settings.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:a",
            "pcm_s16le",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    render_id = str(uuid.uuid4())
    progress: list[int] = []

    result = render_motion_graphics(
        source_path=source,
        render_id=render_id,
        render_format=render_format,
        title="A title with % and :",
        artist_name="Test artist",
        duration_seconds=2,
        progress_callback=progress.append,
    )

    output = render_output_path(render_id)
    assert output.is_file()
    assert result["metadata"] == {
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 1280,
        "height": 720,
        "aspect_ratio": "16:9",
        "duration_seconds": result["metadata"]["duration_seconds"],
        "audio_present": True,
    }
    assert abs(result["metadata"]["duration_seconds"] - 2) <= 1
    assert result["size_bytes"] == output.stat().st_size
    assert len(result["checksum_sha256"]) == 64
    assert result["render_settings"]["uses_uploaded_artwork"] is False
    assert result["render_settings"]["uses_ai_generated_footage"] is False
    assert progress[0] == 10
    assert progress[-1] == 92
    assert not (output.parent / "title.txt").exists()
    assert not (output.parent / "ffmpeg-progress.txt").exists()
