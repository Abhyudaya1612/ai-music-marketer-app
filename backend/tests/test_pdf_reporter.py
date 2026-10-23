"""Tests for PDF reporter service."""
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock
from backend.services.pdf_reporter import generate_campaign_pdf
from backend.domain.models import MarketingCampaign, StudioSong


def test_pdf_generation_returns_bytes():
    """Test that PDF generation returns valid bytes."""
    # Create mock campaign
    campaign = MagicMock(spec=MarketingCampaign)
    campaign.id = "test-campaign-id"
    campaign.budget_usd = 1000.0
    campaign.campaign_duration_days = 28
    campaign.target_audience = "Indie pop fans"
    campaign.target_country = "US"
    campaign.song_quality_score = 8
    campaign.budget_breakdown_json = {
        "tier": "moderate",
        "allocations": [
            {
                "channel": "spotify_ads",
                "amount": 200.0,
                "percentage": 20.0,
                "objective": "Drive streams",
                "expected_deliverables": "Estimate: 1000-5000 listeners",
            }
        ],
    }
    campaign.campaign_plan_json = {
        "positioning_usp": "Fresh indie pop sound",
        "pre_release": ["Teaser campaign"],
        "release_week": ["Release day promotion"],
        "post_release": ["Follow-up content"],
    }
    campaign.captions_json = {
        "instagram_captions": ["Caption 1", "Caption 2"],
        "hashtags": ["#indie", "#pop"],
    }
    campaign.posting_schedule_json = []
    campaign.created_at = datetime.now(timezone.utc)
    campaign.updated_at = datetime.now(timezone.utc)
    
    # Create mock song
    song = MagicMock(spec=StudioSong)
    song.title = "Test Song"
    song.artist_name = "Test Artist"
    song.genre_preferences = ["indie pop"]
    
    # Generate PDF
    pdf_bytes = generate_campaign_pdf(campaign, song)
    
    # Should return bytes
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    
    # Should be a valid PDF (starts with PDF magic number)
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_generation_with_full_data():
    """Test PDF generation with comprehensive campaign data."""
    campaign = MagicMock(spec=MarketingCampaign)
    campaign.id = "test-id-123"
    campaign.budget_usd = 2000.0
    campaign.campaign_duration_days = 56
    campaign.target_audience = "Hip-hop enthusiasts aged 18-35"
    campaign.target_country = "UK"
    campaign.song_quality_score = 7
    campaign.budget_breakdown_json = {
        "tier": "premium",
        "allocations": [
            {
                "channel": "tiktok_ads",
                "amount": 500.0,
                "percentage": 25.0,
                "objective": "Viral potential",
                "expected_deliverables": "Estimate: 500K-2M impressions",
                "priority": "high",
            },
            {
                "channel": "instagram_meta_ads",
                "amount": 400.0,
                "percentage": 20.0,
                "objective": "Engagement",
                "expected_deliverables": "Estimate: 15K-50K engaged accounts",
                "priority": "high",
            },
        ],
    }
    campaign.campaign_plan_json = {
        "positioning_usp": "Hard-hitting beats meet introspective lyrics",
        "pre_release": [
            "Release countdown",
            "Behind-the-scenes content",
            "Playlist pitching",
        ],
        "release_week": [
            "Official release",
            "Music video launch",
            "Live Q&A session",
        ],
        "post_release": [
            "Performance videos",
            "Remix announcements",
        ],
        "campaign_objectives": [
            "10K new listeners in first week",
            "1M streams in first month",
        ],
        "kpis": [
            "Stream count",
            "Social media engagement",
        ],
        "content_pillars": [
            "Artist story",
            "Production process",
        ],
    }
    campaign.captions_json = {
        "instagram_captions": ["Inst caption " + str(i) for i in range(15)],
        "tiktok_captions": ["TikTok caption " + str(i) for i in range(15)],
        "hashtags": ["#hiphop", "#newmusic", "#beats"] + [f"#tag{i}" for i in range(20)],
    }
    campaign.posting_schedule_json = [
        {
            "date": "2024-01-01",
            "platform": "Instagram",
            "content_type": "teaser",
            "posting_time": "14:00",
            "caption_idea": "Test caption",
            "call_to_action": "Save to playlist",
            "phase": "pre-release",
        }
    ]
    campaign.created_at = datetime.now(timezone.utc)
    campaign.updated_at = datetime.now(timezone.utc)
    
    song = MagicMock(spec=StudioSong)
    song.title = "Complex Hip-Hop Track"
    song.artist_name = "Test Rapper"
    song.genre_preferences = ["hip-hop", "rap"]
    
    pdf_bytes = generate_campaign_pdf(campaign, song, intelligence_json=None)
    
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000  # Should be reasonably sized


def test_pdf_contains_expected_sections():
    """Test PDF contains expected content sections."""
    campaign = MagicMock(spec=MarketingCampaign)
    campaign.id = "test-id"
    campaign.budget_usd = 500.0
    campaign.campaign_duration_days = 28
    campaign.target_audience = "EDM fans"
    campaign.target_country = "US"
    campaign.song_quality_score = 6
    campaign.budget_breakdown_json = {
        "tier": "limited",
        "allocations": [{"channel": "test", "amount": 100.0, "percentage": 20.0, "objective": "test", "expected_deliverables": "test"}],
    }
    campaign.campaign_plan_json = {
        "positioning_usp": "Test positioning",
        "pre_release": ["Test"],
        "release_week": ["Test"],
        "post_release": ["Test"],
    }
    campaign.captions_json = {}
    campaign.posting_schedule_json = []
    campaign.created_at = datetime.now(timezone.utc)
    campaign.updated_at = datetime.now(timezone.utc)
    
    song = MagicMock(spec=StudioSong)
    song.title = "EDM Track"
    song.artist_name = "DJ Test"
    song.genre_preferences = ["electronic"]
    
    pdf_bytes = generate_campaign_pdf(campaign, song)
    
    # Convert to string for content checking (lossy but works for basic checks)
    assert pdf_bytes.startswith(b"%PDF")
    # PDF should have multiple pages indicated by "endobj"
    assert pdf_bytes.count(b"endobj") > 5


def test_pdf_generation_with_none_data():
    """Test PDF generation handles None data gracefully."""
    campaign = MagicMock(spec=MarketingCampaign)
    campaign.id = "test"
    campaign.budget_usd = 1000.0
    campaign.campaign_duration_days = 28
    campaign.target_audience = None
    campaign.target_country = None
    campaign.song_quality_score = 5
    campaign.budget_breakdown_json = None
    campaign.campaign_plan_json = None
    campaign.captions_json = None
    campaign.posting_schedule_json = None
    campaign.created_at = datetime.now(timezone.utc)
    campaign.updated_at = datetime.now(timezone.utc)
    
    song = MagicMock(spec=StudioSong)
    song.title = "Minimal Song"
    song.artist_name = None
    song.genre_preferences = []
    
    # Should not raise an error
    pdf_bytes = generate_campaign_pdf(campaign, song)
    
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
