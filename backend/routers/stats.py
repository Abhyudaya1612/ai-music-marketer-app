"""Dashboard aggregate statistics across all analyzed songs."""
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=schemas.StatsOut)
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(models.Song.id)).scalar() or 0
    analyzed = (db.query(func.count(models.Song.id))
                .filter(models.Song.status == "complete").scalar() or 0)
    streams = db.query(func.coalesce(func.sum(models.PerformanceMetricsRow.streams), 0)).scalar()
    views = db.query(func.coalesce(func.sum(models.PerformanceMetricsRow.social_views), 0)).scalar()
    followers = db.query(func.coalesce(func.sum(models.PerformanceMetricsRow.follower_delta), 0)).scalar()
    avg_score = (db.query(func.coalesce(func.avg(models.PerformanceMetricsRow.score), 0))
                 .scalar() or 0.0)

    # top platform by aggregate affinity of primary segments
    top_platform = None
    rows = (db.query(models.AudienceSegmentRow.platform_affinity)
            .filter(models.AudienceSegmentRow.is_primary.is_(True)).all())
    if rows:
        agg: dict[str, float] = {}
        for (pa,) in rows:
            for platform, aff in (pa or {}).items():
                agg[platform] = agg.get(platform, 0.0) + aff
        if agg:
            top_platform = max(agg, key=agg.get)

    active_campaigns = db.query(func.count(models.CampaignPlan.id)).scalar() or 0
    avg_release_window_days = 0.0
    release_dates = db.query(models.CampaignPlan.release_date).filter(models.CampaignPlan.release_date.isnot(None)).all()
    if release_dates:
        days = [max(0, (d[0].date() - datetime.utcnow().date()).days) for d in release_dates if d[0] is not None]
        if days:
            avg_release_window_days = round(sum(days) / len(days), 1)

    artist_profile = db.query(models.ArtistProfile).order_by(models.ArtistProfile.id.desc()).first()
    artist_goals = artist_profile.goals if artist_profile else []

    return schemas.StatsOut(
        total_songs=total, analyzed_songs=analyzed, total_streams=int(streams),
        total_social_views=int(views), total_new_followers=int(followers),
        avg_score=round(float(avg_score), 1), top_platform=top_platform,
        active_campaigns=active_campaigns, avg_release_window_days=avg_release_window_days,
        artist_goals=artist_goals)
