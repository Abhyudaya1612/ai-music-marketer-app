"""Artist profile and release-calendar endpoints."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/artist", tags=["artist"])


@router.get("/profile", response_model=schemas.ArtistProfileOut)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(models.ArtistProfile).order_by(models.ArtistProfile.id.desc()).first()
    if profile is None:
        profile = models.ArtistProfile(
            name="Artist",
            brand_voice="Authentic and community-led",
            target_audience="Gen Z / indie listeners",
            goals=["Grow monthly listeners", "Build social proof", "Release consistently"],
            markets=["Spotify", "TikTok", "Instagram"],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.post("/profile", response_model=schemas.ArtistProfileOut, status_code=201)
def upsert_profile(payload: schemas.ArtistProfileCreate, db: Session = Depends(get_db)):
    profile = db.query(models.ArtistProfile).order_by(models.ArtistProfile.id.desc()).first()
    if profile is None:
        profile = models.ArtistProfile()
        db.add(profile)
    profile.name = payload.name
    profile.brand_voice = payload.brand_voice
    profile.target_audience = payload.target_audience
    profile.goals = payload.goals
    profile.markets = payload.markets
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/calendar", response_model=list[schemas.ReleaseCalendarEntryOut])
def list_calendar(db: Session = Depends(get_db)):
    return db.query(models.ReleaseCalendarEntry).order_by(models.ReleaseCalendarEntry.scheduled_for.asc()).all()


@router.post("/calendar", response_model=schemas.ReleaseCalendarEntryOut, status_code=201)
def create_calendar_entry(payload: schemas.ReleaseCalendarEntryCreate, db: Session = Depends(get_db)):
    if payload.song_id is not None:
        song = db.get(models.Song, payload.song_id)
        if not song:
            raise HTTPException(404, "Song not found")
    if payload.campaign_id is not None:
        campaign = db.get(models.CampaignPlan, payload.campaign_id)
        if not campaign:
            raise HTTPException(404, "Campaign not found")

    entry = models.ReleaseCalendarEntry(
        song_id=payload.song_id,
        campaign_id=payload.campaign_id,
        title=payload.title,
        entry_type=payload.entry_type,
        channel=payload.channel,
        scheduled_for=payload.scheduled_for or datetime.utcnow(),
        status=payload.status,
        notes=payload.notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
