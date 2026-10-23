"""Ollama LLM provider for generating YouTube metadata."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


SANITIZE_PATTERNS = [
    r"ignore\s+previous",
    r"forget\s+everything",
    r"you\s+are\s+now",
    r"pretend",
    r"act\s+as",
    r"system\s+prompt",
]


def _sanitize_input(text: str) -> str:
    """
    Remove prompt-injection patterns from user input.
    
    This is a basic filter; not intended as a security boundary. Ollama's built-in
    safety features provide the primary defense. For production, use Ollama's
    built-in safety features or an external content filter.
    
    Note: Determined attackers can obfuscate injection attempts with whitespace,
    unicode variants, or other encoding techniques. This filter covers common patterns
    but should not be relied upon as the sole defense mechanism.
    """
    # These patterns catch common injection attempts, though attackers can evade them
    # with unicode normalization, extra whitespace, or character substitution
    for pattern in SANITIZE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


@dataclass(frozen=True)
class OllamaMetadata:
    title: str
    description: str
    tags: list[str]


def generate_metadata(
    song_title: str,
    artist_name: str,
    duration_seconds: int,
    features: dict | None = None,
    mood: str | None = None,
) -> OllamaMetadata:
    """Generate YouTube metadata (title, description, tags) via Ollama or fallback to templates."""
    if not settings.ollama_enabled:
        logger.info("ollama_disabled_using_templates")
        return _fallback_metadata(song_title, artist_name, mood)

    # Sanitize inputs
    safe_title = _sanitize_input(song_title)
    safe_artist = _sanitize_input(artist_name)
    safe_mood = _sanitize_input(mood or "")

    prompt = f"""Generate YouTube metadata for this song:
Title: {safe_title}
Artist: {safe_artist}
Duration: {duration_seconds} seconds
Mood: {safe_mood}

Respond with ONLY a valid JSON object (no markdown, no code blocks) with these keys:
- "youtube_title": string, max 100 chars
- "youtube_description": string, max 5000 chars
- "youtube_tags": list of strings, each max 500 chars, total max 10 items

Do not include any explanation, preamble, or markdown formatting."""

    try:
        client = httpx.Client(timeout=settings.ollama_timeout_seconds)
        response = client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        data = response.json()

        # Extract response text
        response_text = data.get("response", "").strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON
        metadata_dict = json.loads(response_text)

        # Validate and extract
        title = str(metadata_dict.get("youtube_title", ""))[:100]
        description = str(metadata_dict.get("youtube_description", ""))[:5000]
        tags = metadata_dict.get("youtube_tags", [])
        if not isinstance(tags, list):
            tags = []
        tags = [str(t)[:500] for t in tags[:10]]

        logger.info(
            "metadata_generated_via_ollama",
            extra={
                "model": settings.ollama_model,
                "response_tokens": data.get("eval_count", 0),
            },
        )

        return OllamaMetadata(title=title, description=description, tags=tags)

    except httpx.ConnectError:
        logger.warning("ollama_connection_refused_using_templates")
        return _fallback_metadata(song_title, artist_name, mood)
    except httpx.TimeoutException:
        logger.warning("ollama_timeout_using_templates")
        return _fallback_metadata(song_title, artist_name, mood)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"ollama_response_invalid_using_templates: {e}")
        return _fallback_metadata(song_title, artist_name, mood)
    except Exception as e:
        logger.error(f"ollama_error_using_templates: {type(e).__name__}: {e}")
        return _fallback_metadata(song_title, artist_name, mood)
    finally:
        try:
            client.close()
        except Exception:
            pass


def _fallback_metadata(song_title: str, artist_name: str, mood: str | None = None) -> OllamaMetadata:
    """Fallback template-based metadata generation."""
    mood_str = f"({mood})" if mood else ""
    title = f"{song_title} - {artist_name} {mood_str}".strip()[:100]
    description = f"Listen to '{song_title}' by {artist_name}. New music now available on all streaming platforms."[:5000]
    tags = [
        song_title[:100],
        artist_name[:100],
        "music",
        "original",
    ]
    if mood:
        tags.append(mood[:100])
    return OllamaMetadata(title=title, description=description, tags=tags[:10])
