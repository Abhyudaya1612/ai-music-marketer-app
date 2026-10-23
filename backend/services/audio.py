"""Audio validation and measured-feature extraction adapters."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..config import settings
from ..core.errors import ApiError
from .storage import derived_path, original_path

logger = logging.getLogger(__name__)

def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def verify_audio(storage_key: str) -> dict[str, Any]:
    _verify_start = time.monotonic()
    source = original_path(storage_key)
    # Simple path check - .env has absolute paths
    ffprobe = Path(settings.ffprobe_path)
    if not source.is_file() or source.stat().st_size == 0:
        raise ApiError(400, "AUDIO_FILE_CORRUPT", "The uploaded audio file is missing or empty.")
    if not (ffprobe.exists() and ffprobe.is_file()):
        raise ApiError(503, "AUDIO_ANALYZER_UNAVAILABLE", "FFprobe is required to validate audio files.")
    try:
        result = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,sample_rate,channels",
                "-of",
                "json",
                str(source),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApiError(503, "AUDIO_ANALYZER_UNAVAILABLE", "The audio validator could not run.") from exc
    if result.returncode != 0:
        raise ApiError(415, "AUDIO_FORMAT_UNSUPPORTED", "The file is not a supported, decodable audio format.")
    try:
        metadata = json.loads(result.stdout)
        audio_streams = [stream for stream in metadata.get("streams", []) if stream.get("codec_type") == "audio"]
        duration = float(metadata.get("format", {}).get("duration", 0))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ApiError(400, "AUDIO_FILE_CORRUPT", "The audio file could not be validated.") from exc
    if not audio_streams or duration <= 0:
        raise ApiError(415, "AUDIO_FORMAT_UNSUPPORTED", "The file does not contain a decodable audio stream.")
    if duration > settings.max_audio_duration_seconds:
        raise ApiError(413, "AUDIO_DURATION_EXCEEDED", "The audio file exceeds the configured duration limit.")
    format_name = metadata.get("format", {}).get("format_name", "unknown")
    formats = set(str(format_name).lower().split(","))
    allowed_formats = {"wav", "mp3", "flac", "ogg", "opus", "aac", "m4a", "mov", "mp4"}
    if not allowed_formats.intersection(formats):
        raise ApiError(415, "AUDIO_FORMAT_UNSUPPORTED", "The uploaded audio format is not supported.")
    stream = audio_streams[0]
    mime_type = (
        "audio/wav" if "wav" in formats
        else "audio/mpeg" if "mp3" in formats
        else "audio/flac" if "flac" in formats
        else "audio/ogg" if formats.intersection({"ogg", "opus"})
        else "audio/aac" if "aac" in formats
        else "audio/mp4" if formats.intersection({"m4a", "mov", "mp4"})
        else "application/octet-stream"
    )
    metadata_result = {
        "duration_seconds": duration,
        "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        "channels": int(stream["channels"]) if stream.get("channels") else None,
        "actual_content_type": mime_type,
    }
    logger.info("verify_audio_completed", extra={
        "duration_seconds": round(duration, 3),
        "sample_rate": metadata_result["sample_rate"],
        "channels": metadata_result["channels"],
    })
    return metadata_result


def extract_features(storage_key: str, checksum: str) -> dict[str, Any]:
    _extract_start = time.monotonic()
    metadata = verify_audio(storage_key)
    # Simple path check - .env has absolute paths
    ffmpeg = Path(settings.ffmpeg_path)
    if not (ffmpeg.exists() and ffmpeg.is_file()):
        raise ApiError(503, "AUDIO_ANALYZER_UNAVAILABLE", "FFmpeg is required to prepare audio for analysis.")
    source = original_path(storage_key)
    derived = derived_path(storage_key)
    derived.parent.mkdir(parents=True, exist_ok=True)
    try:
        converted = subprocess.run(
            [
                str(ffmpeg),
                "-nostdin",
                "-v",
                "info",
                "-i",
                str(source),
                "-vn",
                "-af",
                "silencedetect=noise=-35dB:d=0.75",
                "-ac",
                "1",
                "-ar",
                "22050",
                "-y",
                str(derived),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApiError(503, "AUDIO_PROCESSING_FAILED", "Audio could not be prepared for analysis.") from exc
    if converted.returncode != 0 or not derived.is_file() or derived.stat().st_size == 0:
        derived.unlink(missing_ok=True)
        raise ApiError(400, "AUDIO_FILE_CORRUPT", "Audio could not be decoded for analysis.")

    ffmpeg_version = _ffmpeg_version(ffmpeg)
    features: dict[str, Any] = {
        "duration_seconds": {
            "value": round(metadata["duration_seconds"], 3),
            "status": "measured",
            "unit": "seconds",
            "source": "ffprobe",
            "source_version": ffmpeg_version,
            "limitations": [],
        },
        "sample_rate_hz": {
            "value": metadata["sample_rate"],
            "status": "measured" if metadata["sample_rate"] is not None else "unavailable",
            "unit": "Hz" if metadata["sample_rate"] is not None else None,
            "source": "ffprobe",
            "source_version": ffmpeg_version,
            "limitations": [],
        },
        "channels": {
            "value": metadata["channels"],
            "status": "measured" if metadata["channels"] is not None else "unavailable",
            "unit": "channels" if metadata["channels"] is not None else None,
            "source": "ffprobe",
            "source_version": ffmpeg_version,
            "limitations": [],
        },
    }
    if importlib.util.find_spec("librosa") is not None:
        try:
            features.update(_librosa_features(derived))
        except Exception as exc:
            exc_details = f"{type(exc).__name__}: {str(exc)}"
            logger.error("librosa_feature_extraction_failed reason=%s", exc_details, exc_info=True)
            features["tempo_bpm"] = _unavailable("librosa", f"Librosa analysis failed: {exc_details}")
            features["rms_energy"] = _unavailable("librosa", f"Librosa analysis failed: {exc_details}")
    else:
        features["tempo_bpm"] = _unavailable("librosa", "Librosa is not installed.")
        features["rms_energy"] = _unavailable("librosa", "Librosa is not installed.")
    if importlib.util.find_spec("essentia") is not None:
        try:
            features.update(_essentia_features(derived))
        except Exception as exc:
            exc_details = f"{type(exc).__name__}: {str(exc)}"
            logger.error("essentia_feature_extraction_failed reason=%s", exc_details, exc_info=True)
            features["musical_key"] = _unavailable("essentia", f"Essentia analysis failed: {exc_details}")
    else:
        features["musical_key"] = _unavailable("essentia", "Essentia is not installed.")
    
    result = {
        "audio_features": features,
        "sections": _silence_separated_sections(converted.stderr, metadata["duration_seconds"]),
        "hook_candidates": [],
        "lyrics_analysis": {
            "available": False,
            "themes": [],
            "candidate_lines": [],
            "status": "unavailable",
            "reason": "No lyrics were supplied for this analysis.",
        },
        "predictions": [],
        "limitations": [
            "This analysis reports file measurements and available signal features only.",
            "No listener performance data or private platform data was available.",
            "Section candidates indicate only segments separated by at least 0.75 seconds of audio below -35 dBFS; musical roles and audio hooks are not identified.",
        ],
        "provenance": [
            {
                "component": "audio_pipeline",
                "version": "standard_v1",
                "input_checksum_sha256": checksum,
            },
            {
                "component": "silence_segment_detection",
                "version": ffmpeg_version,
                "threshold_dbfs": -35,
                "minimum_silence_seconds": 0.75,
            },
        ],
    }
    
    logger.info("feature_extraction_completed", extra={
        "duration_ms": round((time.monotonic() - _extract_start) * 1000),
        "librosa_available": importlib.util.find_spec("librosa") is not None,
        "essentia_available": importlib.util.find_spec("essentia") is not None,
    })
    
    return result


def _silence_separated_sections(log_output: str, duration: float) -> list[dict[str, Any]]:
    silence_starts = re.findall(r"silence_start:\s*(-?\d+(?:\.\d+)?)", log_output)
    silence_ends = re.findall(r"silence_end:\s*(-?\d+(?:\.\d+)?)", log_output)
    gaps: list[tuple[float, float]] = []
    end_index = 0
    for start_text in silence_starts:
        start = max(0.0, min(float(start_text), duration))
        while end_index < len(silence_ends) and float(silence_ends[end_index]) < start:
            end_index += 1
        if end_index < len(silence_ends):
            end = max(start, min(float(silence_ends[end_index]), duration))
            end_index += 1
        else:
            end = duration
        gaps.append((start, end))

    segments: list[dict[str, Any]] = []
    cursor = 0.0
    for start, end in gaps:
        if start > cursor:
            segments.append(_section_candidate(cursor, start))
        cursor = max(cursor, end)
    if duration > cursor:
        segments.append(_section_candidate(cursor, duration))
    return segments


def _section_candidate(start: float, end: float) -> dict[str, Any]:
    return {
        "label": "unknown",
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "evidence": "This segment is separated by a detected silence gap; its musical role is undetermined.",
    }


def _librosa_features(path: Path) -> dict[str, Any]:
    import librosa
    import numpy as np

    signal, sample_rate = librosa.load(path, sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=signal, sr=sample_rate)
    tempo_value = float(np.asarray(tempo).reshape(-1)[0]) if np.size(tempo) else None
    rms = librosa.feature.rms(y=signal)
    rms_value = float(np.mean(rms)) if rms.size else None
    version = _version("librosa")
    return {
        "tempo_bpm": {
            "value": round(tempo_value, 2) if tempo_value is not None else None,
            "status": "estimated" if tempo_value is not None else "unavailable",
            "unit": "bpm" if tempo_value is not None else None,
            "source": "librosa",
            "source_version": version,
            "limitations": ["Tempo is an algorithmic estimate and should be reviewed by the artist."],
        },
        "rms_energy": {
            "value": round(rms_value, 6) if rms_value is not None else None,
            "status": "derived" if rms_value is not None else "unavailable",
            "unit": "normalized amplitude" if rms_value is not None else None,
            "source": "librosa",
            "source_version": version,
            "limitations": ["RMS is a signal-level descriptor, not a subjective quality score."],
        },
    }


def _essentia_features(path: Path) -> dict[str, Any]:
    import essentia.standard as es

    try:
        pool = es.MusicExtractor(lowlevelStats=["mean"], rhythmStats=["mean"], tonalStats=["mean"])(str(path))
        key = str(pool["tonal.key_key"])
        bpm = float(pool["rhythm.bpm"])
    except (KeyError, RuntimeError, ValueError):
        return {
            "musical_key": _unavailable("essentia", "Key estimate was unavailable for this file."),
            "essentia_tempo_bpm": _unavailable("essentia", "Tempo estimate was unavailable for this file."),
        }
    version = _version("essentia")
    return {
        "musical_key": {
            "value": key,
            "status": "estimated",
            "unit": None,
            "source": "essentia",
            "source_version": version,
            "limitations": ["Key is an algorithmic estimate; mode and ambiguity are not represented."],
        },
        "essentia_tempo_bpm": {
            "value": bpm,
            "status": "estimated",
            "unit": "bpm",
            "source": "essentia",
            "source_version": version,
            "limitations": ["Tempo is an algorithmic estimate and should be reviewed by the artist."],
        },
    }


def _ffmpeg_version(binary: str) -> str | None:
    try:
        result = subprocess.run(
            [binary, "-version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.splitlines()[0] if result.returncode == 0 and result.stdout else None


def _unavailable(source: str, reason: str) -> dict[str, Any]:
    return {
        "value": None,
        "status": "unavailable",
        "unit": None,
        "source": source,
        "source_version": _version(source),
        "limitations": [reason],
    }
