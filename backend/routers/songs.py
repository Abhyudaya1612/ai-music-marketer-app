"""Song CRUD + pipeline trigger endpoints."""
from __future__ import annotations
import threading
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from .. import models, schemas
from ..workers import execute_pipeline

router = APIRouter(prefix="/api/songs", tags=["songs"])


def _detail_query(db: Session):
    return db.query(models.Song).options(
        selectinload(models.Song.runs).selectinload(models.Run.intelligence),
        selectinload(models.Song.runs).selectinload(models.Run.segments),
        selectinload(models.Song.runs).selectinload(models.Run.content_pieces),
        selectinload(models.Song.runs).selectinload(models.Run.strategy),
        selectinload(models.Song.runs).selectinload(models.Run.metrics),
        selectinload(models.Song.runs).selectinload(models.Run.optimization),
        selectinload(models.Song.runs).selectinload(models.Run.final_strategy),
    )


@router.post("", response_model=schemas.SongOut, status_code=201)
def create_song(payload: schemas.SongCreate, background: BackgroundTasks,
                db: Session = Depends(get_db)):
    """Create a song and automatically run the multi-agent analysis pipeline."""
    song = models.Song(**payload.model_dump())
    db.add(song)
    db.commit()
    db.refresh(song)
    background.add_task(_run_pipeline_background, song.id)
    return song


@router.get("", response_model=list[schemas.SongOut])
def list_songs(db: Session = Depends(get_db)):
    return db.query(models.Song).order_by(models.Song.created_at.desc()).all()


@router.get("/{song_id}", response_model=schemas.SongDetailOutWithCampaigns)
def get_song(song_id: int, db: Session = Depends(get_db)):
    song = (_detail_query(db)
            .options(selectinload(models.Song.campaigns).selectinload(models.CampaignPlan.tasks))
            .filter(models.Song.id == song_id).first())
    if not song:
        raise HTTPException(404, "Song not found")
    return song


@router.post("/{song_id}/campaigns", response_model=schemas.CampaignPlanOut)
def create_campaign(song_id: int, payload: schemas.CampaignPlanCreate, db: Session = Depends(get_db)):
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(404, "Song not found")

    plan = models.CampaignPlan(
        song_id=song.id,
        name=payload.name or f"{song.title} release campaign",
        objective=payload.objective,
        status=payload.status,
        release_date=payload.release_date or __import__("datetime").datetime.utcnow(),
        budget_total=payload.budget_total,
        channels=payload.channels,
        notes=payload.notes,
    )
    db.add(plan)
    db.flush()

    for task_data in payload.tasks[:10]:
        db.add(models.CampaignTask(
            campaign_id=plan.id,
            name=task_data.name,
            channel=task_data.channel,
            owner=task_data.owner,
            priority=task_data.priority,
            due_in_days=task_data.due_in_days,
            status=task_data.status,
            description=task_data.description,
        ))

    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{song_id}", status_code=204)
def delete_song(song_id: int, db: Session = Depends(get_db)):
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(404, "Song not found")
    db.delete(song)
    db.commit()


@router.post("/{song_id}/analyze", response_model=dict)
def reanalyze_song(song_id: int, background: BackgroundTasks,
                   db: Session = Depends(get_db)):
    """Re-run the pipeline for an existing song."""
    song = db.get(models.Song, song_id)
    if not song:
        raise HTTPException(404, "Song not found")
    song.status = "analyzing"
    db.commit()
    background.add_task(_run_pipeline_background, song.id)
    return {"status": "queued", "song_id": song.id}


def _run_pipeline_background(song_id: int):
    """Run pipeline in a daemon thread with its own DB session."""
    t = threading.Thread(target=execute_pipeline, args=(song_id,), daemon=True)
    t.start()
    t.join()
