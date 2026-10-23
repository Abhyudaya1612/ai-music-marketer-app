"""Pipeline worker: execute the multi-agent orchestration and persist
every structured output to the database (one table per agent)."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models
from .engine.pipeline import run_pipeline


def _utcnow():
    return datetime.now(timezone.utc)


def execute_pipeline(song_id: int, db: Session | None = None) -> int:
    """Run the full agent pipeline for a song and store results. Returns run id."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        song = db.get(models.Song, song_id)
        if not song:
            raise ValueError(f"Song {song_id} not found")

        song.status = "analyzing"
        run = models.Run(song_id=song.id, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            result = run_pipeline({
                "title": song.title, "artist": song.artist, "genre": song.genre,
                "lyrics": song.lyrics, "bpm": song.bpm, "musical_key": song.musical_key,
                "energy": song.energy, "valence": song.valence,
            })
            _persist_run(db, run, result)
            run.status = "finished"
            song.status = "complete"
        except Exception as exc:  # noqa: BLE001 — record any pipeline failure
            run.status = "failed"
            run.error = str(exc)
            song.status = "failed"
        run.finished_at = _utcnow()
        db.commit()
        return run.id
    finally:
        if owns_session:
            db.close()


def _persist_run(db: Session, run: models.Run, result: dict):
    intel = result["song_intelligence"]
    db.add(models.SongIntelligenceRow(
        run_id=run.id, bpm=intel["bpm"], musical_key=intel["musical_key"],
        energy=intel["energy"], valence=intel["valence"], mood=intel["mood"],
        structure=intel["structure"], hooks=intel["hooks"],
        lyrical_themes=intel["lyrical_themes"], production_notes=intel["production_notes"],
        a_r_insights=intel["a_r_insights"]))
    run.logs = result["logs"]

    aud = result["audience"]
    for rank, seg in enumerate(aud["segments"]):
        db.add(models.AudienceSegmentRow(
            run_id=run.id, name=seg["name"], description=seg["description"],
            age_range=seg["age_range"], interests=seg["interests"],
            platform_affinity=seg["platform_affinity"], match_score=seg["match_score"],
            is_primary=(seg["name"] == aud["primary_segment"]), rank=rank))

    for i, piece in enumerate(result["content_plan"]["pieces"]):
        db.add(models.ContentPieceRow(
            run_id=run.id, format=piece["format"], hook=piece["hook"],
            concept=piece["concept"], caption=piece["caption"], cta=piece["cta"],
            sound_strategy=piece["sound_strategy"], sort_index=i))

    strat = result["marketing_strategy"]
    db.add(models.MarketingStrategyRow(
        run_id=run.id, release_type=strat["release_type"],
        timeline_weeks=strat["timeline_weeks"], phases=strat["phases"],
        platform_priority=strat["platform_priority"],
        budget_allocation=strat["budget_allocation"],
        pitch_targets=strat["pitch_targets"], key_message=strat["key_message"]))

    met = result["optimization"]["metrics"]
    db.add(models.PerformanceMetricsRow(
        run_id=run.id, streams=met["streams"], saves=met["saves"],
        playlist_adds=met["playlist_adds"], social_views=met["social_views"],
        engagement_rate=met["engagement_rate"], follower_delta=met["follower_delta"],
        score=met["score"]))

    opt = result["optimization"]
    db.add(models.OptimizationReportRow(
        run_id=run.id, what_worked=opt["what_worked"],
        what_underperformed=opt["what_underperformed"],
        recommendations=opt["recommendations"], lessons_learned=opt["lessons_learned"]))

    fin = result["final"]
    db.add(models.FinalStrategyRow(
        run_id=run.id, orchestrator_summary=fin["orchestrator_summary"],
        top_priority_actions=fin["top_priority_actions"]))
    db.flush()
