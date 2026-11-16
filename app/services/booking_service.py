"""Logica aplicației pentru rezervări."""

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.services import facility_service


class SlotNotFoundError(Exception):
    """Slotul cerut nu există."""


class FacilityNotBookableError(Exception):
    """Facilitatea slotului e în mentenanță sau inactivă."""


class SlotNotAvailableError(Exception):
    """Slotul nu mai este liber (rezervat sau blocat)."""


class SlotAlreadyStartedError(Exception):
    """Slotul a început deja (sau a trecut) și nu mai poate fi rezervat."""


def has_started(db: Session, slot: TimeSlot) -> bool:
    """Spune dacă slotul a început deja, după ora României."""
    now = facility_service.romania_now(db)
    return (slot.slot_date, slot.start_time) <= (now.date(), now.time())


def create_booking(db: Session, user_id: int, slot_id: int) -> Booking:
    """Rezervă slotul pentru utilizator; slotul devine „booked”.

    Ridică SlotNotFoundError, FacilityNotBookableError,
    SlotAlreadyStartedError sau SlotNotAvailableError dacă rezervarea nu se
    poate face.
    """
    slot = db.get(TimeSlot, slot_id)
    if slot is None:
        raise SlotNotFoundError()
    if db.get(Facility, slot.facility_id).status != "active":
        raise FacilityNotBookableError()
    if has_started(db, slot):
        raise SlotAlreadyStartedError()

    # Ocupăm slotul cu o singură comandă, care îl schimbă doar dacă e liber.
    # Dacă două cereri vin în același timp, baza de date le execută pe rând,
    # iar a doua nu mai găsește slotul liber (0 rânduri modificate).
    result = db.execute(
        update(TimeSlot)
        .where(TimeSlot.id == slot_id, TimeSlot.status == "free")
        .values(status="booked")
    )
    if result.rowcount == 0:
        db.rollback()
        raise SlotNotAvailableError()

    # Data creării se salvează în UTC, ca să nu depindă de fusul orar al
    # serverului de bază de date (local e ora României, pe Neon e UTC).
    booking = Booking(
        user_id=user_id,
        slot_id=slot_id,
        created_at=func.timezone("UTC", func.now()),
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as error:
        # A doua protecție: indexul unic permite o singură rezervare
        # confirmată pe slot.
        db.rollback()
        raise SlotNotAvailableError() from error
    db.refresh(booking)
    return booking
