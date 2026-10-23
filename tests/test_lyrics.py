from backend.services.lyrics import analyze_lyrics


def test_lyrics_analysis_reports_only_supported_themes_and_repeated_lines():
    result = analyze_lyrics("Neon on the water\nI miss the city\nNeon on the water")

    assert result["available"] is True
    assert result["themes"] == ["nightlife and escape", "loss and longing"]
    assert result["candidate_lines"] == [
        {
            "text": "Neon on the water",
            "evidence": "This artist-supplied line repeats 2 times in the submitted lyrics.",
            "occurrences": 2,
        }
    ]


def test_lyrics_analysis_marks_missing_text_unavailable():
    result = analyze_lyrics("  \n ")

    assert result["available"] is False
    assert result["status"] == "unavailable"
    assert result["themes"] == []
    assert result["candidate_lines"] == []


def test_lyrics_analysis_does_not_invent_hook_for_unique_lines():
    result = analyze_lyrics("The road is quiet\nMorning finds the window")

    assert result["candidate_lines"] == []
