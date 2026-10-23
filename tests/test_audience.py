from backend.domain.models import ArtistWorkspaceProfile, StudioSong
from backend.services.audience import build_audience_hypotheses


def test_audience_hypotheses_are_evidence_linked_and_non_demographic():
    song = StudioSong(genre_preferences=["indie pop"])
    profile = ArtistWorkspaceProfile(
        language="English",
        territories=["Canada"],
        goals=["find early listeners"],
        primary_genre="indie pop",
    )

    result = build_audience_hypotheses(
        "analysis-1",
        {"lyrics_analysis": {"themes": ["self-discovery"]}},
        song,
        profile,
    )

    assert len(result.hypotheses) == 1
    hypothesis = result.hypotheses[0]
    assert hypothesis.evidence[0].source == "lyrics_analysis.themes"
    assert hypothesis.evidence[0].status == "keyword_derived"
    assert "Canada" in " ".join(hypothesis.artist_context)
    assert "English" in " ".join(hypothesis.artist_context)
    assert "demographic" in hypothesis.uncertainty
    assert "recommendation-system" in " ".join(result.limitations)


def test_audience_service_does_not_invent_hypotheses_without_song_evidence():
    result = build_audience_hypotheses(
        "analysis-2",
        {"lyrics_analysis": {"themes": []}},
        StudioSong(genre_preferences=[]),
        None,
    )

    assert result.hypotheses == []
