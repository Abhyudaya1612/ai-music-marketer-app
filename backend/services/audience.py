"""Evidence-linked audience hypotheses that do not infer demographics."""
from __future__ import annotations

from typing import Any

from ..domain.models import ArtistWorkspaceProfile, StudioSong
from ..domain.schemas import AudienceEvidence, AudienceHypothesesOut, AudienceHypothesis


def build_audience_hypotheses(
    analysis_id: str,
    intelligence: dict[str, Any],
    song: StudioSong,
    profile: ArtistWorkspaceProfile | None,
) -> AudienceHypothesesOut:
    artist_context = []
    if profile is not None:
        artist_context.extend(f"Artist-selected territory: {territory}" for territory in profile.territories)
        if profile.language:
            artist_context.append(f"Artist-selected language: {profile.language}")
        artist_context.extend(f"Artist-stated goal: {goal}" for goal in profile.goals)
    artist_context.extend(
        f"Artist-selected genre: {genre}" for genre in (song.genre_preferences or [])
    )
    if not song.genre_preferences and profile is not None and profile.primary_genre:
        artist_context.append(f"Artist-selected genre: {profile.primary_genre}")

    themes = intelligence.get("lyrics_analysis", {}).get("themes", [])
    hypotheses = [
        AudienceHypothesis(
            statement=(
                f"Listeners who voluntarily engage with {theme} narratives may be worth "
                "exploring for this song."
            ),
            evidence=[
                AudienceEvidence(
                    source="lyrics_analysis.themes",
                    observation=f"Artist-supplied lyrics matched the local keyword theme: {theme}.",
                    status="keyword_derived",
                )
            ],
            artist_context=artist_context,
            uncertainty=(
                "Keyword matching does not establish listener preference, demographic fit, "
                "platform reach, or likely performance."
            ),
            validation_experiment=(
                "The artist can share a short excerpt with an artist-selected, relevant "
                "listener group and record qualitative reactions without collecting "
                "unnecessary personal data."
            ),
        )
        for theme in themes[:3]
    ]
    return AudienceHypothesesOut(
        analysis_id=analysis_id,
        hypotheses=hypotheses,
        limitations=[
            "No authorized historical performance or listener data was available.",
            "No demographic, platform-affinity, reach, or recommendation-system claims are made.",
            "Artist-selected territories, languages, goals, and genres are planning context, not audience observations.",
        ],
    )
