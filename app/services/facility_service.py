"""Logica aplicației pentru facilități."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.schemas.facility import FacilityData


class FacilityHasSlotsError(Exception):
    """Facilitatea are intervale în calendar și nu poate fi ștearsă."""


def list_facilities(db: Session) -> list[Facility]:
    """Întoarce toate facilitățile, în ordinea în care au fost adăugate."""
    return list(db.scalars(select(Facility).order_by(Facility.id)))


def get_facility(db: Session, facility_id: int) -> Facility | None:
    """Întoarce facilitatea cu id-ul dat sau None dacă nu există."""
    return db.get(Facility, facility_id)


def create_facility(db: Session, data: FacilityData) -> Facility:
    """Adaugă o facilitate nouă."""
    facility = Facility(**data.to_db_values())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility


def update_facility(db: Session, facility: Facility, data: FacilityData) -> Facility:
    """Înlocuiește datele unei facilități existente."""
    for column, value in data.to_db_values().items():
        setattr(facility, column, value)
    db.commit()
    db.refresh(facility)
    return facility


def delete_facility(db: Session, facility: Facility) -> None:
    """Șterge o facilitate care nu are intervale în calendar.

    Facilitățile cu intervale se dezactivează în loc să fie șterse, ca să
    rămână istoricul rezervărilor (vezi specificația API).
    """
    # Tabelul time_slot nu are încă model în cod, așa că verificăm direct în SQL.
    has_slots = db.scalar(
        text("SELECT EXISTS (SELECT 1 FROM time_slot WHERE facility_id = :id)"),
        {"id": facility.id},
    )
    if has_slots:
        raise FacilityHasSlotsError
    db.delete(facility)
    db.commit()
