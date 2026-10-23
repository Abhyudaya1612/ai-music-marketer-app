from __future__ import annotations

import importlib.util
import math
import shutil
import struct
import uuid
import wave

import pytest

from backend.config import settings
from backend.services.audio import _silence_separated_sections, extract_features, verify_audio
from backend.services.storage import original_path


@pytest.mark.skipif(
    shutil.which(settings.ffprobe_path) is None or shutil.which(settings.ffmpeg_path) is None,
    reason="FFmpeg and FFprobe are required for this integration test.",
)
def test_audio_is_decoded_and_measured_without_changing_original(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "private"))
    storage_key = str(uuid.uuid4())
    source = original_path(storage_key)
    source.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050
    frames = (
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
        for index in range(sample_rate)
    )
    with wave.open(str(source), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(2)
        audio_file.setframerate(sample_rate)
        audio_file.writeframes(b"".join(frames))
    original_bytes = source.read_bytes()

    metadata = verify_audio(storage_key)
    result = extract_features(storage_key, "a" * 64)

    assert metadata["duration_seconds"] == pytest.approx(1.0, abs=0.02)
    assert metadata["sample_rate"] == sample_rate
    assert metadata["actual_content_type"] == "audio/wav"
    assert result["audio_features"]["duration_seconds"]["status"] == "measured"
    assert result["audio_features"]["duration_seconds"]["value"] == pytest.approx(1.0, abs=0.02)
    assert result["provenance"][0]["input_checksum_sha256"] == "a" * 64
    assert source.read_bytes() == original_bytes
    assert (source.parent / "analysis.wav").is_file()


@pytest.mark.skipif(
    shutil.which(settings.ffprobe_path) is None or shutil.which(settings.ffmpeg_path) is None,
    reason="FFmpeg and FFprobe are required for this integration test.",
)
def test_real_audio_feature_extraction_with_librosa(monkeypatch, tmp_path):
    """Test real audio feature extraction using librosa and essentia when available.
    
    This test creates a 2-second stereo 44100 Hz test audio and verifies:
    - duration_seconds is measured via ffprobe (status=measured)
    - sample_rate_hz is measured via ffprobe (status=measured)
    - tempo_bpm is estimated via librosa if available (status=estimated or unavailable)
    - rms_energy is derived via librosa if available (status=derived or unavailable)
    - musical_key is estimated via essentia if available (status=estimated or unavailable)
    
    No exact BPM or key values are asserted; only status fields and reasonable ranges.
    """
    monkeypatch.setattr(settings, "media_storage_path", str(tmp_path / "private"))
    storage_key = str(uuid.uuid4())
    source = original_path(storage_key)
    source.parent.mkdir(parents=True, exist_ok=True)
    
    # Create a 2-second stereo 44100 Hz sine wave WAV
    sample_rate = 44100
    duration_seconds = 2
    num_samples = sample_rate * duration_seconds
    num_channels = 2
    
    frames = (
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate)))
        for index in range(num_samples)
    )
    
    with wave.open(str(source), "wb") as audio_file:
        audio_file.setnchannels(num_channels)
        audio_file.setsampwidth(2)
        audio_file.setframerate(sample_rate)
        # Interleave stereo: duplicate the mono data for both channels
        stereo_frames = b""
        for mono_sample in b"".join(frames):
            stereo_frames += bytes([mono_sample]) * num_channels
        audio_file.writeframes(stereo_frames)
    
    metadata = verify_audio(storage_key)
    result = extract_features(storage_key, "b" * 64)
    
    # Verify measured fields (ffprobe)
    assert result["audio_features"]["duration_seconds"]["status"] == "measured"
    assert result["audio_features"]["duration_seconds"]["value"] == pytest.approx(2.0, abs=0.05)
    assert result["audio_features"]["sample_rate_hz"]["status"] == "measured"
    assert result["audio_features"]["sample_rate_hz"]["value"] == 44100
    
    # Verify librosa features if available
    if importlib.util.find_spec("librosa") is not None:
        tempo = result["audio_features"]["tempo_bpm"]
        assert tempo["status"] in ("estimated", "unavailable")
        if tempo["status"] == "estimated":
            assert 20 <= tempo["value"] <= 400, "Tempo should be within reasonable BPM range"
        
        rms = result["audio_features"]["rms_energy"]
        assert rms["status"] in ("derived", "unavailable")
        if rms["status"] == "derived":
            assert rms["value"] > 0, "RMS energy should be positive"
    
    # Verify essentia features if available
    if importlib.util.find_spec("essentia") is not None:
        key = result["audio_features"]["musical_key"]
        assert key["status"] in ("estimated", "unavailable")
        if key["status"] == "estimated":
            assert isinstance(key["value"], str) and len(key["value"]) > 0
    
    # Verify provenance is non-empty
    assert len(result["provenance"]) > 0


def test_silence_detection_creates_only_neutral_section_candidates():
    log_output = (
        "[silencedetect] silence_start: 3.25\n"
        "[silencedetect] silence_end: 4.5 | silence_duration: 1.25\n"
        "[silencedetect] silence_start: 8\n"
    )

    sections = _silence_separated_sections(log_output, 10)

    assert sections == [
        {
            "label": "unknown",
            "start_seconds": 0.0,
            "end_seconds": 3.25,
            "evidence": "This segment is separated by a detected silence gap; its musical role is undetermined.",
        },
        {
            "label": "unknown",
            "start_seconds": 4.5,
            "end_seconds": 8.0,
            "evidence": "This segment is separated by a detected silence gap; its musical role is undetermined.",
        },
    ]
