"""Logica aplicației pentru facilități."""

from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.schemas.facility import FacilityData, FacilityFilters

# Cea mai mare valoare pe care o poate stoca o coloană INT din PostgreSQL.
MAX_DB_ID = 2_147_483_647

# „Azi” înseamnă ziua din România, indiferent unde rulează serverul.
ROMANIA_TIMEZONE = "Europe/Bucharest"


class FacilityHasSlotsError(Exception):
    """Facilitatea are intervale în calendar și nu poate fi ștearsă."""


def romania_now(db: Session) -> datetime:
    """Data și ora de acum în România, fără fus orar atașat.

    Ora se ia de la PostgreSQL, care are tabelul fusurilor orare inclus;
    așa nu e nevoie de un pachet în plus în Python.
    """
    return db.scalar(select(func.timezone(ROMANIA_TIMEZONE, func.now())))


def list_facilities(db: Session, filters: FacilityFilters) -> list[Facility]:
    """Întoarce catalogul: facilitățile active care respectă filtrele date.

    Facilitățile în mentenanță sau inactive nu se pot rezerva, deci nu apar
    în catalog. Ordinea este cea în care au fost adăugate.
    """
    query = select(Facility).where(Facility.status == "active")
    if filters.search is not None:
        # autoescape: „%” și „_” din text se caută ca atare, nu ca șabloane SQL.
        query = query.where(Facility.name.icontains(filters.search, autoescape=True))
    if filters.sport is not None:
        query = query.where(func.lower(Facility.sport) == filters.sport.lower())
    if filters.min_capacity is not None:
        query = query.where(Facility.capacity >= filters.min_capacity)
    if filters.available_today:
        now = romania_now(db)
        # Un interval liber azi, care nu a început încă (se mai poate rezerva).
        free_slot_today = select(TimeSlot.id).where(
            TimeSlot.facility_id == Facility.id,
            TimeSlot.status == "free",
            TimeSlot.slot_date == now.date(),
            TimeSlot.start_time > now.time(),
        )
        query = query.where(free_slot_today.exists())
    return list(db.scalars(query.order_by(Facility.id)))


def list_all_facilities(db: Session) -> list[Facility]:
    """Întoarce toate facilitățile, indiferent de status (pentru administrare)."""
    return list(db.scalars(select(Facility).order_by(Facility.id)))


def get_facility(db: Session, facility_id: int) -> Facility | None:
    """Întoarce facilitatea cu id-ul dat sau None dacă nu există."""
    # Un id în afara intervalului unei coloane INT nu poate exista în baza de
    # date; fără această verificare, PostgreSQL ar da eroare (500).
    if not 1 <= facility_id <= MAX_DB_ID:
        return None
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
