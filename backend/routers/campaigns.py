"""Song promotion & marketing campaign endpoints."""
from __future__ import annotations

import logging
from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from .. import domain
from ..core.auth import current_owner
from ..database import get_db
from ..domain import models, schemas
from ..services.budget_calculator import (
    calculate_budget_breakdown,
    calculate_reach_projection,
    calculate_song_quality_score,
)
from ..services.campaign_planner import (
    generate_campaign_plan,
    generate_captions_and_concepts,
    generate_posting_schedule,
)
from ..services.pdf_reporter import generate_campaign_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("", response_model=schemas.MarketingCampaignOut, status_code=201)
def create_campaign(
    payload: schemas.MarketingCampaignCreate,
    owner_id: str = Depends(current_owner),
    db: Session = Depends(get_db),
):
    """Create a new marketing campaign for a song."""
    
    # Validate song exists and owner matches
    song = db.query(models.StudioSong).filter(
        models.StudioSong.id == payload.song_id,
        models.StudioSong.owner_id == owner_id,
    ).first()
    
    if not song:
        raise HTTPException(404, "Song not found")
    
    if payload.budget_usd < 100:
        raise HTTPException(400, "Budget must be at least $100")
    
    # Calculate budget breakdown deterministically
    budget_breakdown = calculate_budget_breakdown(payload.budget_usd)
    reach_projection = calculate_reach_projection(payload.budget_usd)
    
    # Generate campaign plan
    campaign_plan = generate_campaign_plan(
        intelligence_json=None,
        song=song,
        budget=payload.budget_usd,
        goals=[payload.goals] if payload.goals else None,
        target_audience=payload.target_audience,
        release_date=payload.release_date,
    )
    
    # Generate captions and concepts
    captions_and_concepts = generate_captions_and_concepts(
        intelligence_json=None,
        song=song,
        target_platforms=["Instagram", "TikTok", "YouTube", "Twitter"],
    )
    
    # Generate posting schedule
    posting_schedule = generate_posting_schedule(
        campaign_duration_days=payload.campaign_duration_days,
        release_date=payload.release_date,
        num_posts=payload.campaign_duration_days,
    )
    
    # Calculate song quality score
    song_quality_score = calculate_song_quality_score()
    
    # Create campaign record
    campaign = models.MarketingCampaign(
        owner_id=owner_id,
        song_id=payload.song_id,
        budget_usd=payload.budget_usd,
        release_date=payload.release_date,
        campaign_duration_days=payload.campaign_duration_days,
        target_audience=payload.target_audience,
        target_country=payload.target_country,
        goals=payload.goals,
        marketing_mix_preference=_determine_marketing_mix(payload),
        artist_audience_size=payload.artist_audience_size,
        prefer_organic=payload.prefer_organic,
        prefer_paid_ads=payload.prefer_paid_ads,
        prefer_influencer=payload.prefer_influencer,
        campaign_plan_json=campaign_plan,
        budget_breakdown_json=budget_breakdown,
        captions_json=captions_and_concepts,
        posting_schedule_json=posting_schedule,
        song_quality_score=song_quality_score,
        reach_projection=reach_projection,
        ollama_model_used="phi",
    )
    
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    logger.info("campaign_created", extra={"campaign_id": campaign.id, "song_id": payload.song_id})
    
    return _format_campaign_out(campaign)


@router.get("", response_model=schemas.MarketingCampaignListOut)
def list_campaigns(
    owner_id: str = Depends(current_owner),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all marketing campaigns for the authenticated user."""
    
    total_count = db.query(models.MarketingCampaign).filter(
        models.MarketingCampaign.owner_id == owner_id
    ).count()
    
    campaigns = db.query(models.MarketingCampaign).filter(
        models.MarketingCampaign.owner_id == owner_id
    ).order_by(
        models.MarketingCampaign.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return schemas.MarketingCampaignListOut(
        items=[_format_campaign_out(c) for c in campaigns],
        next_cursor=str(skip + limit) if skip + limit < total_count else None,
        total_count=total_count,
    )


@router.get("/{campaign_id}", response_model=schemas.MarketingCampaignOut)
def get_campaign(
    campaign_id: str,
    owner_id: str = Depends(current_owner),
    db: Session = Depends(get_db),
):
    """Get a specific marketing campaign."""
    
    campaign = db.query(models.MarketingCampaign).filter(
        models.MarketingCampaign.id == campaign_id,
        models.MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    
    return _format_campaign_out(campaign)


@router.get("/{campaign_id}/report.pdf")
def download_campaign_report(
    campaign_id: str,
    owner_id: str = Depends(current_owner),
    db: Session = Depends(get_db),
):
    """Download the campaign report as a PDF."""
    
    campaign = db.query(models.MarketingCampaign).filter(
        models.MarketingCampaign.id == campaign_id,
        models.MarketingCampaign.owner_id == owner_id,
    ).options(selectinload(models.MarketingCampaign.song)).first()
    
    if not campaign or not campaign.song:
        raise HTTPException(404, "Campaign not found")
    
    # Generate PDF
    pdf_buffer = generate_campaign_pdf(
        song_title=campaign.song.title,
        artist_name=campaign.song.artist_name or "Unknown",
        genre=campaign.song.genre_preferences[0] if campaign.song.genre_preferences else "General",
        budget_usd=campaign.budget_usd,
        budget_breakdown=campaign.budget_breakdown_json,
        captions=campaign.captions_json,
        posting_schedule=campaign.posting_schedule_json,
        campaign_plan=campaign.campaign_plan_json,
        song_quality_score=campaign.song_quality_score,
        reach_projection=campaign.reach_projection,
        release_date=campaign.release_date,
    )
    
    if pdf_buffer is None:
        raise HTTPException(
            503,
            "PDF generation is not available. reportlab may not be installed.",
        )
    
    return FileResponse(
        pdf_buffer,
        media_type="application/pdf",
        filename=f"campaign_{campaign.song.title.replace(' ', '_')}.pdf",
    )


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: str,
    owner_id: str = Depends(current_owner),
    db: Session = Depends(get_db),
):
    """Delete a marketing campaign."""
    
    campaign = db.query(models.MarketingCampaign).filter(
        models.MarketingCampaign.id == campaign_id,
        models.MarketingCampaign.owner_id == owner_id,
    ).first()
    
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    
    db.delete(campaign)
    db.commit()
    
    logger.info("campaign_deleted", extra={"campaign_id": campaign_id})


def _determine_marketing_mix(payload: schemas.MarketingCampaignCreate) -> str:
    """Determine the marketing mix preference from user inputs."""
    if payload.prefer_organic and not payload.prefer_paid_ads and not payload.prefer_influencer:
        return "organic_only"
    elif payload.prefer_paid_ads and not payload.prefer_organic and not payload.prefer_influencer:
        return "paid_ads_only"
    elif payload.prefer_influencer and not payload.prefer_organic and not payload.prefer_paid_ads:
        return "influencer_only"
    elif payload.prefer_organic and payload.prefer_paid_ads:
        return "organic_and_paid"
    elif payload.prefer_paid_ads and payload.prefer_influencer:
        return "paid_and_influencer"
    elif payload.prefer_organic and payload.prefer_influencer:
        return "organic_and_influencer"
    elif payload.prefer_organic and payload.prefer_paid_ads and payload.prefer_influencer:
        return "balanced"
    else:
        return "balanced"


def _format_campaign_out(campaign: models.MarketingCampaign) -> schemas.MarketingCampaignOut:
    """Convert database model to output schema."""
    
    # Convert budget breakdown to list format
    budget_list = []
    for platform_key, details in campaign.budget_breakdown_json.items():
        if isinstance(details, dict):
            budget_list.append(schemas.BudgetAllocationItem(
                platform=details.get("platform", platform_key),
                amount_usd=details.get("amount_usd", 0),
                percentage=details.get("percentage", 0),
                objective=details.get("objective", ""),
                deliverables=details.get("deliverables", ""),
                priority=details.get("priority", ""),
            ))
    
    return schemas.MarketingCampaignOut(
        campaign_id=campaign.id,
        song_id=campaign.song_id,
        budget_usd=campaign.budget_usd,
        release_date=campaign.release_date,
        campaign_duration_days=campaign.campaign_duration_days,
        target_audience=campaign.target_audience,
        target_country=campaign.target_country,
        goals=campaign.goals,
        artist_audience_size=campaign.artist_audience_size,
        marketing_mix_preference=campaign.marketing_mix_preference,
        song_quality_score=campaign.song_quality_score,
        reach_projection=campaign.reach_projection,
        budget_breakdown=budget_list,
        captions=campaign.captions_json,
        posting_schedule=campaign.posting_schedule_json,
        campaign_plan=campaign.campaign_plan_json,
        ollama_model_used=campaign.ollama_model_used,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )

