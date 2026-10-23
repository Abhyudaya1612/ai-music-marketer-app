"""Deterministic budget allocation for marketing campaigns (no LLM)."""
from __future__ import annotations

from datetime import date
from typing import Any


def allocate_budget(total_budget: float, goals: list[str] | None = None) -> dict[str, Any]:
    """
    Allocate total budget deterministically across marketing channels.
    
    Args:
        total_budget: Total promotional budget in USD (must be >= 100)
        goals: Optional list of campaign goals (for context only; allocation is fixed)
        
    Returns:
        dict with:
            - tier: 'limited' (<500), 'moderate' (500-1500), 'premium' (>1500)
            - total_budget: float
            - allocations: list of dicts with channel, amount, percentage, objective, 
                          expected_deliverables, priority
            - zero_budget_organic_strategy: list of organic tactics if budget is low
    """
    if total_budget < 100.0:
        raise ValueError(f"Budget must be at least $100 USD. Got ${total_budget}")
    
    # Determine tier based on budget
    if total_budget < 500:
        tier = "limited"
    elif total_budget <= 1500:
        tier = "moderate"
    else:
        tier = "premium"
    
    # Fixed allocation percentages across channels
    allocations_pct = {
        "spotify_ads": 0.20,
        "tiktok_ads": 0.25,
        "instagram_meta_ads": 0.20,
        "youtube_ads": 0.20,
        "influencer_outreach": 0.15,
    }
    
    allocations = []
    for channel, pct in allocations_pct.items():
        amount = total_budget * pct
        
        # Tailor objective and deliverables by channel
        if channel == "spotify_ads":
            objective = "Drive playlist placements and streaming volume on Spotify"
            deliverables = "Estimate: 500-2000 new monthly listeners (limited tier)"
            if tier == "moderate":
                deliverables = "Estimate: 1500-5000 new monthly listeners"
            elif tier == "premium":
                deliverables = "Estimate: 4000-12000 new monthly listeners"
        elif channel == "tiktok_ads":
            objective = "Maximize organic reach via TikTok viral potential and paid amplification"
            deliverables = "Estimate: 50K-200K impressions (limited tier)"
            if tier == "moderate":
                deliverables = "Estimate: 200K-800K impressions"
            elif tier == "premium":
                deliverables = "Estimate: 500K-2M impressions"
        elif channel == "instagram_meta_ads":
            objective = "Engage audience on Instagram Reels and convert followers"
            deliverables = "Estimate: 1000-5000 engaged accounts (limited tier)"
            if tier == "moderate":
                deliverables = "Estimate: 5000-20000 engaged accounts"
            elif tier == "premium":
                deliverables = "Estimate: 15000-50000 engaged accounts"
        elif channel == "youtube_ads":
            objective = "Promote lyric video or music video on YouTube"
            deliverables = "Estimate: 10K-50K video views (limited tier)"
            if tier == "moderate":
                deliverables = "Estimate: 50K-200K video views"
            elif tier == "premium":
                deliverables = "Estimate: 200K-800K video views"
        elif channel == "influencer_outreach":
            objective = "Partner with micro/nano influencers for authentic promotion"
            deliverables = "Estimate: 2-5 collaborations (limited tier)"
            if tier == "moderate":
                deliverables = "Estimate: 5-15 collaborations"
            elif tier == "premium":
                deliverables = "Estimate: 15-40 collaborations"
        
        allocations.append({
            "channel": channel,
            "amount": round(amount, 2),
            "percentage": round(pct * 100, 1),
            "objective": objective,
            "expected_deliverables": deliverables,
            "priority": "high" if pct >= 0.20 else "medium",
        })
    
    # Verify allocations sum to 100%
    total_pct = sum(a["percentage"] for a in allocations)
    assert abs(total_pct - 100.0) < 0.1, f"Allocations do not sum to 100%: {total_pct}"
    
    # Zero-budget organic strategy (always provided as fallback advice)
    organic_strategy = [
        {
            "action": "Post consistently on owned channels",
            "description": "Share behind-the-scenes content, lyric snippets, and production stories on TikTok, Instagram Reels, and YouTube Shorts 3-5 times per week.",
            "frequency": "3-5x per week",
        },
        {
            "action": "Engage with community",
            "description": "Comment on and share content from similar artists and playlist curators. Build genuine relationships with your audience.",
            "frequency": "Daily",
        },
        {
            "action": "Pitch to playlists manually",
            "description": "Submit to independent playlist curators and platform editorial playlists (Spotify, Apple Music, YouTube).",
            "frequency": "Weekly (on release week and 2 weeks before)",
        },
        {
            "action": "Leverage TikTok sounds",
            "description": "Encourage users to create content with your song's audio. Use trending sounds and participate in challenges.",
            "frequency": "Ongoing, especially pre-release and release week",
        },
        {
            "action": "Collaborate with other artists",
            "description": "Partner with musicians at your level or growing artists for cross-promotion and remix opportunities.",
            "frequency": "Monthly or as opportunities arise",
        },
    ]
    
    return {
        "tier": tier,
        "total_budget": round(total_budget, 2),
        "allocations": allocations,
        "zero_budget_organic_strategy": organic_strategy,
    }


def zero_budget_organic_strategy() -> list[dict[str, str]]:
    """Return organic tactics for campaigns with minimal budget."""
    return [
        {
            "action": "Post consistently on owned channels",
            "description": "Share behind-the-scenes content, lyric snippets, and production stories on TikTok, Instagram Reels, and YouTube Shorts 3-5 times per week.",
            "frequency": "3-5x per week",
        },
        {
            "action": "Engage with community",
            "description": "Comment on and share content from similar artists and playlist curators. Build genuine relationships with your audience.",
            "frequency": "Daily",
        },
        {
            "action": "Pitch to playlists manually",
            "description": "Submit to independent playlist curators and platform editorial playlists (Spotify, Apple Music, YouTube).",
            "frequency": "Weekly (on release week and 2 weeks before)",
        },
        {
            "action": "Leverage TikTok sounds",
            "description": "Encourage users to create content with your song's audio. Use trending sounds and participate in challenges.",
            "frequency": "Ongoing, especially pre-release and release week",
        },
        {
            "action": "Collaborate with other artists",
            "description": "Partner with musicians at your level or growing artists for cross-promotion and remix opportunities.",
            "frequency": "Monthly or as opportunities arise",
        },
    ]


def calculate_budget_breakdown(budget_usd: float) -> dict[str, Any]:
    """Convert allocate_budget output to a simpler format for API responses."""
    result = allocate_budget(budget_usd)
    breakdown = {}
    for alloc in result["allocations"]:
        platform_key = alloc["channel"].replace("_ads", "").replace("_outreach", "").replace("_meta", "")
        breakdown[platform_key] = {
            "platform": _format_platform_name(alloc["channel"]),
            "amount_usd": alloc["amount"],
            "percentage": alloc["percentage"],
            "objective": alloc["objective"],
            "deliverables": alloc["expected_deliverables"],
            "priority": alloc["priority"],
        }
    return breakdown


def calculate_reach_projection(budget_usd: float) -> int:
    """Estimate reach based on budget tier."""
    if budget_usd < 500:
        return int(budget_usd * 50)
    elif budget_usd < 1500:
        return int(budget_usd * 100)
    else:
        return int(budget_usd * 150)


def calculate_song_quality_score(
    audio_analysis: dict | None = None,
    lyrics_analysis: dict | None = None,
) -> int:
    """Calculate a song quality score (1-10) based on available analysis."""
    score = 5
    
    if audio_analysis:
        if audio_analysis.get("loudness_db", -20) > -15:
            score += 1
        if audio_analysis.get("clarity_score", 0) > 0.7:
            score += 1
    
    if lyrics_analysis:
        if lyrics_analysis.get("unique_lines_count", 0) > 20:
            score += 1
        if lyrics_analysis.get("rhyme_scheme_detected", False):
            score += 1
    
    return min(10, max(1, score))


def _format_platform_name(channel: str) -> str:
    """Format channel name for display."""
    mapping = {
        "spotify_ads": "Spotify Playlist Pitching",
        "tiktok_ads": "TikTok Promotion",
        "instagram_meta_ads": "Instagram/Meta Advertising",
        "youtube_ads": "YouTube Advertising",
        "influencer_outreach": "Influencer Collaborations",
    }
    return mapping.get(channel, channel)
