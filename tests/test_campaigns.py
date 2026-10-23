"""Test marketing campaigns endpoints and services."""
import os
import tempfile
import pytest

# Set database URL before importing app
db_file = tempfile.mktemp(suffix='.db')
os.environ["APP_DATABASE_URL"] = f"sqlite:///{db_file}"

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db, init_db, SessionLocal
from backend.domain.models import StudioSong, MarketingCampaign, new_id, utcnow
from backend.services.budget_calculator import (
    calculate_budget_breakdown,
    calculate_reach_projection,
)
from backend.services.campaign_planner import (
    generate_captions_and_concepts,
    generate_posting_schedule,
)
from backend.config import settings


@pytest.fixture(autouse=True, scope="function")
def setup_db():
    """Initialize the database before each test."""
    init_db()
    yield


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Generate valid auth headers."""
    return {"Authorization": f"Bearer {settings.api_token}"}


@pytest.fixture
def test_song():
    """Create a test song."""
    db = SessionLocal()
    try:
        song = StudioSong(
            id=new_id(),
            owner_id=settings.auth_user_id,
            title="Test Song",
            artist_name="Test Artist",
            genre_preferences=["pop", "dance"],
            language="en",
        )
        db.add(song)
        db.commit()
        db.refresh(song)
        return song
    finally:
        db.close()



class TestBudgetCalculator:
    """Test deterministic budget allocation."""
    
    def test_budget_breakdown_100_dollars(self):
        """Test budget allocation for $100."""
        breakdown = calculate_budget_breakdown(100)
        
        assert breakdown["spotify"]["amount_usd"] == 20.0
        assert breakdown["tiktok"]["amount_usd"] == 25.0
        assert breakdown["instagram"]["amount_usd"] == 20.0
        assert breakdown["youtube"]["amount_usd"] == 20.0
        assert breakdown["influencer"]["amount_usd"] == 15.0
        
        total = sum(v["amount_usd"] for v in breakdown.values())
        assert total == 100.0
    
    def test_budget_breakdown_500_dollars(self):
        """Test budget allocation for $500."""
        breakdown = calculate_budget_breakdown(500)
        
        total = sum(v["amount_usd"] for v in breakdown.values())
        assert total == 500.0
        assert breakdown["spotify"]["percentage"] == 20.0
    
    def test_budget_breakdown_1500_dollars(self):
        """Test budget allocation for $1500."""
        breakdown = calculate_budget_breakdown(1500)
        
        total = sum(v["amount_usd"] for v in breakdown.values())
        assert total == 1500.0
        assert breakdown["tiktok"]["amount_usd"] == 375.0
    
    def test_reach_projection_under_500(self):
        """Test reach projection for budget < $500."""
        reach = calculate_reach_projection(100)
        assert reach == 5000  # 100 * 50
    
    def test_reach_projection_500_to_1500(self):
        """Test reach projection for budget $500-$1500."""
        reach = calculate_reach_projection(500)
        assert reach == 50000  # 500 * 100
        
        reach = calculate_reach_projection(1000)
        assert reach == 100000  # 1000 * 100
    
    def test_reach_projection_over_1500(self):
        """Test reach projection for budget > $1500."""
        reach = calculate_reach_projection(2000)
        assert reach == 300000  # 2000 * 150


class TestCampaignPlanner:
    """Test campaign planning services."""
    
    def test_generate_captions_returns_valid_structure(self):
        """Test that captions generation returns expected structure."""
        from backend.domain.models import StudioSong, new_id
        song = StudioSong(
            id=new_id(),
            owner_id="test-owner",
            title="Test Song",
            artist_name="Test Artist",
            genre_preferences=["pop"],
        )
        
        captions = generate_captions_and_concepts(
            intelligence_json=None,
            song=song,
            target_platforms=["Instagram", "TikTok", "YouTube"],
        )
        
        assert "instagram_captions" in captions
        assert "tiktok_captions" in captions
        assert "video_concepts" in captions
        assert "hashtags" in captions
        
        assert isinstance(captions["instagram_captions"], list)
        assert isinstance(captions["tiktok_captions"], list)
        assert isinstance(captions["hashtags"], list)
        
        assert len(captions["instagram_captions"]) >= 3
        assert len(captions["hashtags"]) >= 5
    
    def test_generate_posting_schedule_returns_valid_structure(self):
        """Test that posting schedule generation returns expected structure."""
        schedule = generate_posting_schedule(
            song_title="Test Song",
            release_date="2024-12-01",
            campaign_duration_days=28,
        )
        
        assert isinstance(schedule, list)
        assert len(schedule) > 0
        
        # Check structure of first item
        item = schedule[0]
        assert "day" in item
        assert "platform" in item
        assert "content_format" in item
        assert "caption" in item
        assert "objective" in item
        assert "call_to_action" in item


class TestCampaignEndpoints:
    """Test marketing campaign API endpoints."""
    
    def test_create_campaign_minimum_budget(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test creating a campaign with minimum $100 budget."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
                "campaign_duration_days": 28,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["budget_usd"] == 100
        assert data["song_id"] == test_song.id
        assert data["song_quality_score"] > 0
        assert data["reach_projection"] > 0
        assert len(data["budget_breakdown"]) == 5  # 5 platforms
    
    def test_create_campaign_500_dollars(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test creating a campaign with $500 budget."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 500,
                "target_audience": "18-25 year old music listeners",
                "target_country": "US",
                "goals": "Maximize streams and engagement",
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["budget_usd"] == 500
        assert data["target_audience"] == "18-25 year old music listeners"
        assert data["reach_projection"] == 50000  # 500 * 100
    
    def test_create_campaign_1500_dollars(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test creating a campaign with $1500 budget."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 1500,
                "prefer_organic": True,
                "prefer_paid_ads": True,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["budget_usd"] == 1500
        assert data["reach_projection"] == 225000  # 1500 * 150
        assert "captions" in data
        assert "posting_schedule" in data
    
    def test_create_campaign_2000_dollars(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test creating a campaign with $2000 budget."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 2000,
                "prefer_influencer": True,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["reach_projection"] == 300000  # 2000 * 150
    
    def test_create_campaign_budget_too_low(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test that campaign creation fails with budget < $100."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 50,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 400
    
    def test_create_campaign_invalid_song(self, client: TestClient, auth_headers: dict):
        """Test that campaign creation fails with invalid song ID."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": "invalid-song-id",
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    def test_list_campaigns(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test listing campaigns."""
        # Create a campaign
        create_response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        
        # List campaigns
        response = client.get("/api/v1/campaigns", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert data["total_count"] >= 1
    
    def test_get_campaign(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test getting a specific campaign."""
        # Create a campaign
        create_response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        campaign_id = create_response.json()["campaign_id"]
        
        # Get campaign
        response = client.get(f"/api/v1/campaigns/{campaign_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == campaign_id
        assert data["budget_usd"] == 100
    
    def test_get_nonexistent_campaign(self, client: TestClient, auth_headers: dict):
        """Test getting a nonexistent campaign."""
        response = client.get(
            "/api/v1/campaigns/nonexistent-id",
            headers=auth_headers,
        )
        assert response.status_code == 404
    
    def test_delete_campaign(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test deleting a campaign."""
        # Create a campaign
        create_response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        campaign_id = create_response.json()["campaign_id"]
        
        # Delete campaign
        response = client.delete(
            f"/api/v1/campaigns/{campaign_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = client.get(
            f"/api/v1/campaigns/{campaign_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404
    
    def test_campaign_contains_budget_breakdown(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test that campaign contains detailed budget breakdown."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        
        data = response.json()
        breakdown = data["budget_breakdown"]
        
        assert len(breakdown) == 5
        platforms = [item["platform"] for item in breakdown]
        assert any("Spotify" in p for p in platforms)
        assert any("TikTok" in p for p in platforms)
        assert any("Instagram" in p for p in platforms)
        assert any("YouTube" in p for p in platforms)
        assert any("Influencer" in p for p in platforms)
        
        # Verify percentages
        total_percentage = sum(item["percentage"] for item in breakdown)
        assert total_percentage == 100.0
    
    def test_campaign_contains_captions(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test that campaign contains social media captions."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        
        data = response.json()
        captions = data["captions"]
        
        assert "instagram_captions" in captions
        assert "tiktok_captions" in captions
        assert "hashtags" in captions
        assert len(captions["instagram_captions"]) >= 3
        assert len(captions["hashtags"]) >= 5
    
    def test_campaign_contains_posting_schedule(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test that campaign contains a posting schedule."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        
        data = response.json()
        schedule = data["posting_schedule"]
        
        assert isinstance(schedule, list)
        assert len(schedule) > 0
        
        # Check structure of first item
        first_item = schedule[0]
        assert "day" in first_item
        assert "platform" in first_item
        assert "content_format" in first_item
        assert "objective" in first_item
    
    def test_download_pdf_report(self, client: TestClient, auth_headers: dict, test_song: StudioSong):
        """Test downloading PDF report (if reportlab is available)."""
        # Create a campaign
        create_response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
            headers=auth_headers,
        )
        campaign_id = create_response.json()["campaign_id"]
        
        # Download PDF
        response = client.get(
            f"/api/v1/campaigns/{campaign_id}/report.pdf",
            headers=auth_headers,
        )
        
        # PDF might not be available if reportlab is not installed
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            assert response.headers["content-type"] == "application/pdf"
            assert len(response.content) > 0


class TestAuthRequired:
    """Test authentication requirements."""
    
    def test_create_campaign_without_auth(self, client: TestClient, test_song: StudioSong):
        """Test that campaign creation requires authentication."""
        response = client.post(
            "/api/v1/campaigns",
            json={
                "song_id": test_song.id,
                "budget_usd": 100,
            },
        )
        assert response.status_code == 403
    
    def test_list_campaigns_without_auth(self, client: TestClient):
        """Test that listing campaigns requires authentication."""
        response = client.get("/api/v1/campaigns")
        assert response.status_code == 403
