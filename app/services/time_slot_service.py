"""Logica aplicației pentru intervalele din calendar (sloturi)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_slot import TimeSlot

# Perioada maximă care poate fi cerută odată, ca să încapă o lună întreagă
# fără ca cineva să poată cere ani de calendar într-o singură cerere.
MAX_PERIOD_DAYS = 31


class InvalidPeriodError(Exception):
    """Perioada cerută nu este validă (ordinea datelor sau lungimea ei)."""


def check_period(start: date, end: date) -> None:
    """Verifică dacă perioada cerută este corectă; altfel ridică InvalidPeriodError."""
    if start > end:
        raise InvalidPeriodError("Data de început este după data de sfârșit.")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise InvalidPeriodError(
            f"Perioada cerută poate avea cel mult {MAX_PERIOD_DAYS} de zile."
        )


def list_slots(db: Session, facility_id: int, start: date, end: date) -> list[TimeSlot]:
    """Întoarce sloturile facilității din perioada dată, în ordinea din calendar."""
    check_period(start, end)
    query = (
        select(TimeSlot)
        .where(
            TimeSlot.facility_id == facility_id,
            TimeSlot.slot_date >= start,
            TimeSlot.slot_date <= end,
        )
        .order_by(TimeSlot.slot_date, TimeSlot.start_time)
    )
    return list(db.scalars(query))
