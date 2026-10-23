"""Run inspection endpoints (status, agent audit logs)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = (db.query(models.Run)
           .options(selectinload(models.Run.intelligence),
                    selectinload(models.Run.segments),
                    selectinload(models.Run.content_pieces),
                    selectinload(models.Run.strategy),
                    selectinload(models.Run.metrics),
                    selectinload(models.Run.optimization),
                    selectinload(models.Run.final_strategy))
           .filter(models.Run.id == run_id).first())
    if not run:
        raise HTTPException(404, "Run not found")
    return run
