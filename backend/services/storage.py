"""Private local media storage adapter."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import UUID

from starlette.requests import Request

from ..config import settings
from ..core.errors import ApiError


def storage_root() -> Path:
    root = Path(settings.media_storage_path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def asset_directory(storage_key: str) -> Path:
    key = str(UUID(storage_key))
    directory = (storage_root() / key).resolve()
    if directory.parent != storage_root():
        raise ApiError(400, "VALIDATION_ERROR", "Invalid asset identifier.")
    return directory


def original_path(storage_key: str) -> Path:
    return asset_directory(storage_key) / "original"


def derived_path(storage_key: str) -> Path:
    return asset_directory(storage_key) / "analysis.wav"


def render_output_path(render_id: str) -> Path:
    return asset_directory(render_id) / "render.mp4"


async def write_upload(
    request: Request,
    storage_key: str,
    expected_size_bytes: int,
) -> tuple[int, str]:
    directory = asset_directory(storage_key)
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / "upload.part"
    target = original_path(storage_key)
    digest = hashlib.sha256()
    total = 0
    try:
        with temp_path.open("wb") as destination:
            async for chunk in request.stream():
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise ApiError(413, "AUDIO_FILE_TOO_LARGE", "The audio file exceeds the configured size limit.")
                if total > expected_size_bytes:
                    raise ApiError(400, "UPLOAD_SIZE_MISMATCH", "The uploaded file exceeds the declared upload size.")
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if total == 0:
            raise ApiError(400, "AUDIO_FILE_CORRUPT", "The uploaded file is empty.")
        if total != expected_size_bytes:
            raise ApiError(400, "UPLOAD_SIZE_MISMATCH", "The uploaded file does not match the declared upload size.")
        temp_path.replace(target)
        return total, digest.hexdigest()
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
