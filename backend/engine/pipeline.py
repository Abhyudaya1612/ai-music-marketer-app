"""Pipeline entrypoint: run the full multi-agent orchestration for a song
and return everything as plain dicts, ready for DB persistence."""
from __future__ import annotations
from .schemas import SongInput, to_dict
from .orchestrator import MusicMarketerOrchestrator


def run_pipeline(song_data: dict) -> dict:
    logs: list[str] = []
    song = SongInput(
        title=song_data["title"],
        artist=song_data["artist"],
        genre=song_data.get("genre", ""),
        lyrics=song_data.get("lyrics", ""),
        bpm=song_data.get("bpm"),
        musical_key=song_data.get("musical_key"),
        energy=song_data.get("energy"),
        valence=song_data.get("valence"),
    )
    orchestrator = MusicMarketerOrchestrator(log_sink=logs)
    results = orchestrator.run(song)
    return {
        "logs": logs,
        "song_intelligence": to_dict(results["song_intelligence"]),
        "audience": to_dict(results["audience"]),
        "content_plan": to_dict(results["content_plan"]),
        "marketing_strategy": to_dict(results["marketing_strategy"]),
        "optimization": to_dict(results["optimization"]),
        "final": results["final"],
    }
