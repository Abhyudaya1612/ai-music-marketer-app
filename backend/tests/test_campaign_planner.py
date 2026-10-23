"""Tests for campaign planner service."""
from datetime import date, timedelta
import pytest
from unittest.mock import MagicMock
from backend.services.campaign_planner import (
    check_ollama_available,
    generate_song_quality_report,
    generate_campaign_plan,
    generate_captions_and_concepts,
    generate_posting_schedule,
)
from backend.domain.models import StudioSong


def test_check_ollama_available():
    """Test Ollama availability check returns bool."""
    result = check_ollama_available()
    assert isinstance(result, bool)


def test_generate_song_quality_report_fallback():
    """Test song quality report generation with fallback."""
    song = MagicMock(spec=StudioSong)
    song.title = "Test Song"
    song.artist_name = "Test Artist"
    song.genre_preferences = ["pop"]
    
    result = generate_song_quality_report(None, song)
    
    # Should have required keys
    assert "score" in result
    assert "strengths" in result
    assert "weaknesses" in result
    assert "audience_hypotheses" in result
    assert "genre_positioning" in result
    assert "commercial_observations" in result
    
    # Validate types
    assert isinstance(result["score"], int)
    assert 1 <= result["score"] <= 10
    assert isinstance(result["strengths"], list)
    assert isinstance(result["weaknesses"], list)
    assert isinstance(result["audience_hypotheses"], list)
    assert isinstance(result["genre_positioning"], str)
    assert isinstance(result["commercial_observations"], str)
    
    # Should be marked as AI Assessment
    assert "AI Assessment:" in result["commercial_observations"]


def test_generate_campaign_plan_fallback():
    """Test campaign plan generation with fallback."""
    song = MagicMock(spec=StudioSong)
    song.title = "Test Song"
    song.artist_name = "Test Artist"
    song.genre_preferences = ["indie"]
    
    result = generate_campaign_plan(
        None,
        song,
        budget=1000.0,
        goals=["Build awareness"],
        target_audience="Indie fans",
        release_date=date.today(),
    )
    
    # Should have required keys
    assert "pre_release" in result
    assert "release_week" in result
    assert "post_release" in result
    assert "campaign_objectives" in result
    assert "kpis" in result
    assert "content_pillars" in result
    assert "positioning_usp" in result
    
    # Validate types
    assert isinstance(result["pre_release"], list)
    assert isinstance(result["release_week"], list)
    assert isinstance(result["post_release"], list)
    assert len(result["pre_release"]) > 0
    assert len(result["release_week"]) > 0
    assert len(result["post_release"]) > 0


def test_generate_captions_and_concepts_fallback():
    """Test captions and concepts generation with fallback."""
    song = MagicMock(spec=StudioSong)
    song.title = "Test Song"
    song.artist_name = "Test Artist"
    song.genre_preferences = ["pop"]
    
    result = generate_captions_and_concepts(None, song, ["Instagram", "TikTok"])
    
    # Should have required keys
    assert "instagram_captions" in result
    assert "tiktok_captions" in result
    assert "twitter_captions" in result
    assert "video_concepts" in result
    assert "hashtags" in result
    assert "cta_examples" in result
    
    # Validate types and minimum counts
    assert isinstance(result["instagram_captions"], list)
    assert len(result["instagram_captions"]) >= 10
    assert isinstance(result["tiktok_captions"], list)
    assert len(result["tiktok_captions"]) >= 10
    assert isinstance(result["video_concepts"], list)
    assert len(result["video_concepts"]) >= 10


def test_generate_posting_schedule():
    """Test posting schedule generation."""
    release_date = date.today()
    result = generate_posting_schedule(
        campaign_duration_days=28,
        release_date=release_date,
        num_posts=28,
    )
    
    # Should return a list
    assert isinstance(result, list)
    assert len(result) > 0
    
    # Each post should have required fields
    for post in result:
        assert "date" in post
        assert "day" in post
        assert "posting_time" in post
        assert "platform" in post
        assert "content_type" in post
        assert "caption_idea" in post
        assert "call_to_action" in post
        assert "phase" in post
    
    # Check phases are reasonable
    phases = {p["phase"] for p in result}
    assert len(phases) > 0


def test_generate_posting_schedule_multi_week():
    """Test posting schedule generation for multiple weeks."""
    release_date = date.today()
    result = generate_posting_schedule(
        campaign_duration_days=56,
        release_date=release_date,
        num_posts=56,
    )
    
    assert len(result) > 0
    
    # Should have posts from different days
    days = {p["day"] for p in result}
    assert len(days) > 1


def test_generate_posting_schedule_platform_rotation():
    """Test that posting schedule rotates through platforms."""
    release_date = date.today()
    result = generate_posting_schedule(
        campaign_duration_days=28,
        release_date=release_date,
    )
    
    platforms = [p["platform"] for p in result]
    
    # Should have multiple platforms
    unique_platforms = set(platforms)
    assert len(unique_platforms) > 1


def test_generate_posting_schedule_content_type_rotation():
    """Test that posting schedule rotates through content types."""
    release_date = date.today()
    result = generate_posting_schedule(
        campaign_duration_days=28,
        release_date=release_date,
    )
    
    content_types = [p["content_type"] for p in result]
    
    # Should have multiple content types
    unique_content_types = set(content_types)
    assert len(unique_content_types) > 1


def test_campaign_plan_includes_positioning():
    """Test campaign plan includes USP positioning."""
    song = MagicMock(spec=StudioSong)
    song.title = "Test Song"
    song.artist_name = "Test Artist"
    song.genre_preferences = ["electronic"]
    
    result = generate_campaign_plan(
        None, song, 1000.0, [], "Electronic music fans", date.today()
    )
    
    assert "positioning_usp" in result
    assert result["positioning_usp"]  # Should not be empty


def test_song_quality_report_has_score():
    """Test song quality report has valid score."""
    song = MagicMock(spec=StudioSong)
    song.title = "Test"
    song.artist_name = "Artist"
    song.genre_preferences = []
    
    result = generate_song_quality_report(None, song)
    
    assert "score" in result
    assert isinstance(result["score"], int)
    assert 1 <= result["score"] <= 10
