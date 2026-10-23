"""Consent state lookup shared by API handlers and in-process workers."""
from sqlalchemy.orm import Session

from ..domain.models import ConsentRecord


def has_active_consent(
    db: Session,
    owner_id: str,
    consent_type: str,
    song_id: str | None,
) -> bool:
    scoped = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.owner_id == owner_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.song_id == song_id,
        )
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .first()
    )
    if scoped is not None:
        return bool(scoped.granted)
    if song_id is None:
        return False
    workspace = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.owner_id == owner_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.song_id.is_(None),
        )
        .order_by(ConsentRecord.created_at.desc(), ConsentRecord.id.desc())
        .first()
    )
    return bool(workspace and workspace.granted)
