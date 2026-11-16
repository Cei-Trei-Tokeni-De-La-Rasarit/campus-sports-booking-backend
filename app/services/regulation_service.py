"""Logica aplicației pentru regulamentele facilităților."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.regulation import Regulation


def get_regulation(db: Session, facility_id: int) -> Regulation | None:
    """Întoarce regulamentul unei facilități sau None dacă nu există."""
    return db.scalar(select(Regulation).where(Regulation.facility_id == facility_id))
