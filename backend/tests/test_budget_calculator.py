"""Tests for budget calculator service."""
import pytest
from backend.services.budget_calculator import allocate_budget, zero_budget_organic_strategy


def test_budget_calculator_valid_small_budget():
    """Test budget allocation for small budget."""
    result = allocate_budget(300.0, [])
    assert result["tier"] == "limited"
    assert result["total_budget"] == 300.0
    assert len(result["allocations"]) == 5
    
    # Check allocations sum to 100%
    total_pct = sum(a["percentage"] for a in result["allocations"])
    assert abs(total_pct - 100.0) < 0.1
    
    # Check total amount equals budget
    total_amount = sum(a["amount"] for a in result["allocations"])
    assert abs(total_amount - 300.0) < 0.01


def test_budget_calculator_valid_medium_budget():
    """Test budget allocation for medium budget."""
    result = allocate_budget(1000.0, ["Build awareness"])
    assert result["tier"] == "moderate"
    assert result["total_budget"] == 1000.0
    
    total_pct = sum(a["percentage"] for a in result["allocations"])
    assert abs(total_pct - 100.0) < 0.1
    
    total_amount = sum(a["amount"] for a in result["allocations"])
    assert abs(total_amount - 1000.0) < 0.01


def test_budget_calculator_valid_large_budget():
    """Test budget allocation for large budget."""
    result = allocate_budget(3000.0, [])
    assert result["tier"] == "premium"
    assert result["total_budget"] == 3000.0


def test_budget_calculator_minimum_budget_error():
    """Test that budget < $100 raises ValueError."""
    with pytest.raises(ValueError, match="Budget must be at least"):
        allocate_budget(50.0, [])


def test_budget_calculator_tier_boundaries():
    """Test tier assignment at boundaries."""
    result_limited = allocate_budget(499.0, [])
    assert result_limited["tier"] == "limited"
    
    result_moderate = allocate_budget(500.0, [])
    assert result_moderate["tier"] == "moderate"
    
    result_premium = allocate_budget(1501.0, [])
    assert result_premium["tier"] == "premium"


def test_budget_calculator_allocation_channels():
    """Test that all expected channels are present."""
    result = allocate_budget(1000.0, [])
    channels = {a["channel"] for a in result["allocations"]}
    
    expected_channels = {
        "spotify_ads",
        "tiktok_ads",
        "instagram_meta_ads",
        "youtube_ads",
        "influencer_outreach",
    }
    assert channels == expected_channels


def test_budget_calculator_allocation_priorities():
    """Test that priorities are set correctly."""
    result = allocate_budget(1000.0, [])
    high_priority = [a for a in result["allocations"] if a["priority"] == "high"]
    assert len(high_priority) > 0
    
    # High priority channels should be >= 20%
    for alloc in high_priority:
        assert alloc["percentage"] >= 20.0


def test_budget_calculator_organic_strategy():
    """Test zero-budget organic strategy."""
    strategy = zero_budget_organic_strategy()
    assert isinstance(strategy, list)
    assert len(strategy) >= 3
    
    # Each item should have action, description, frequency
    for item in strategy:
        assert "action" in item
        assert "description" in item
        assert "frequency" in item


def test_budget_calculator_allocations_include_deliverables():
    """Test that allocations include expected_deliverables."""
    result = allocate_budget(1000.0, [])
    
    for alloc in result["allocations"]:
        assert "expected_deliverables" in alloc
        assert "Estimate:" in alloc["expected_deliverables"]
        assert alloc["expected_deliverables"]  # Should not be empty
