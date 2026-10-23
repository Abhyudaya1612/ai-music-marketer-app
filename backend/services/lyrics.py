"""Local-only analysis for lyrics supplied directly by an authorized artist."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

THEME_TERMS = {
    "love and relationships": {"love", "heart", "kiss", "darling", "together"},
    "nightlife and escape": {"night", "neon", "city", "drive", "lights"},
    "ambition and success": {"grind", "win", "money", "crown", "empire"},
    "loss and longing": {"gone", "miss", "empty", "ghost", "without"},
    "self-discovery": {"mirror", "change", "become", "myself", "identity"},
}


def _normalize_line(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", normalized))


def analyze_lyrics(lyrics: str | None) -> dict:
    if not lyrics or not lyrics.strip():
        return {
            "available": False,
            "status": "unavailable",
            "themes": [],
            "candidate_lines": [],
            "reason": "No lyrics were supplied for this analysis.",
        }

    lines = [line.strip() for line in lyrics.splitlines() if line.strip()]
    normalized_lines = [_normalize_line(line) for line in lines]
    counts = Counter(line for line in normalized_lines if line)
    representative_lines: dict[str, str] = {}
    for original, normalized in zip(lines, normalized_lines):
        if normalized:
            representative_lines.setdefault(normalized, original)

    repeated_lines = [
        {
            "text": representative_lines[line],
            "evidence": f"This artist-supplied line repeats {count} times in the submitted lyrics.",
            "occurrences": count,
        }
        for line, count in counts.most_common()
        if count > 1
    ][:5]
    words = set(re.findall(r"\w+", _normalize_line(lyrics)))
    themes = [
        theme
        for theme, terms in THEME_TERMS.items()
        if words.intersection(terms)
    ]
    return {
        "available": True,
        "status": "analyzed",
        "themes": themes,
        "candidate_lines": repeated_lines,
        "reason": (
            "Themes are keyword-based and repeated lines are candidates only; "
            "neither indicates listener response or commercial effectiveness."
        ),
    }
