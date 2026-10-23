"""Engine unit tests — pure stdlib, no external services needed."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from engine.pipeline import run_pipeline  # noqa: E402

SONG = dict(title="Neon Skyline", artist="The Midnight Runners", genre="indie electronic",
            lyrics=chr(10).join(["We were born to outrun the night", "City lights",
                               "We were born to outrun the night"]))


def test_pipeline_returns_all_agent_outputs():
    out = run_pipeline(SONG)
    for key in ["logs", "song_intelligence", "audience", "content_plan",
                "marketing_strategy", "optimization", "final"]:
        assert key in out


def test_music_analysis_structure():
    intel = run_pipeline(SONG)["song_intelligence"]
    assert 40 <= intel["bpm"] <= 220
    assert intel["musical_key"]
    assert 0 <= intel["energy"] <= 1
    assert len(intel["hooks"]) >= 1
    assert "nightlife & escape" in intel["lyrical_themes"]


def test_audience_ranking():
    aud = run_pipeline(SONG)["audience"]
    scores = [s["match_score"] for s in aud["segments"]]
    assert scores == sorted(scores, reverse=True)
    assert aud["primary_segment"] == aud["segments"][0]["name"]


def test_content_and_strategy_consistency():
    out = run_pipeline(SONG)
    assert len(out["content_plan"]["pieces"]) == 5
    strat = out["marketing_strategy"]
    assert strat["timeline_weeks"] >= 4
    assert abs(sum(strat["budget_allocation"].values()) - 100) < 1e-6


def test_metrics_and_final_actions():
    out = run_pipeline(SONG)
    m = out["optimization"]["metrics"]
    assert m["streams"] > 0 and 0 <= m["score"] <= 100
    assert len(out["final"]["top_priority_actions"]) == 4
