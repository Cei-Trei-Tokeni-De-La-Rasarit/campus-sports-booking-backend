"""Logica aplicației pentru rezervări."""

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.services import facility_service

# Câte rezervări care nu au început încă poate avea un utilizator odată,
# ca un singur cont să nu poată ocupa tot calendarul.
MAX_ACTIVE_BOOKINGS = 3


class SlotNotFoundError(Exception):
    """Slotul cerut nu există."""


class FacilityNotBookableError(Exception):
    """Facilitatea slotului e în mentenanță sau inactivă."""


class SlotNotAvailableError(Exception):
    """Slotul nu mai este liber (rezervat sau blocat)."""


class SlotAlreadyStartedError(Exception):
    """Slotul a început deja (sau a trecut) și nu mai poate fi rezervat."""


class OverlappingBookingError(Exception):
    """Utilizatorul are deja o rezervare care se suprapune cu slotul cerut."""


class TooManyBookingsError(Exception):
    """Utilizatorul are deja numărul maxim de rezervări active."""


def has_started(db: Session, slot: TimeSlot) -> bool:
    """Spune dacă slotul a început deja, după ora României."""
    now = facility_service.romania_now(db)
    return (slot.slot_date, slot.start_time) <= (now.date(), now.time())


def has_overlapping_booking(db: Session, user_id: int, slot: TimeSlot) -> bool:
    """Spune dacă utilizatorul are o rezervare confirmată în același interval.

    Două intervale din aceeași zi se suprapun dacă fiecare începe înainte să
    se termine celălalt (10:00-11:00 și 11:00-12:00 nu se suprapun).
    """
    query = (
        select(Booking.id)
        .join(TimeSlot, Booking.slot_id == TimeSlot.id)
        .where(
            Booking.user_id == user_id,
            Booking.status == "confirmed",
            TimeSlot.slot_date == slot.slot_date,
            TimeSlot.start_time < slot.end_time,
            TimeSlot.end_time > slot.start_time,
        )
    )
    return db.scalar(query.exists().select()) is True


def count_active_bookings(db: Session, user_id: int) -> int:
    """Numărul rezervărilor confirmate ale utilizatorului care nu au început."""
    now = facility_service.romania_now(db)
    not_started = or_(
        TimeSlot.slot_date > now.date(),
        and_(TimeSlot.slot_date == now.date(), TimeSlot.start_time > now.time()),
    )
    query = (
        select(func.count())
        .select_from(Booking)
        .join(TimeSlot, Booking.slot_id == TimeSlot.id)
        .where(Booking.user_id == user_id, Booking.status == "confirmed", not_started)
    )
    return db.scalar(query)


def create_booking(db: Session, user_id: int, slot_id: int) -> Booking:
    """Rezervă slotul pentru utilizator; slotul devine „booked”.

    Ridică SlotNotFoundError, FacilityNotBookableError,
    SlotAlreadyStartedError, OverlappingBookingError, TooManyBookingsError sau
    SlotNotAvailableError dacă rezervarea nu se poate face.
    """
    slot = db.get(TimeSlot, slot_id)
    if slot is None:
        raise SlotNotFoundError()
    if db.get(Facility, slot.facility_id).status != "active":
        raise FacilityNotBookableError()
    if has_started(db, slot):
        raise SlotAlreadyStartedError()

    # Blocăm rândul utilizatorului până la finalul tranzacției: dacă același
    # cont trimite mai multe rezervări deodată, ele se verifică pe rând, ca
    # regulile de mai jos (suprapunere, maxim) să nu poată fi ocolite.
    db.execute(select(User.id).where(User.id == user_id).with_for_update())
    if has_overlapping_booking(db, user_id, slot):
        db.rollback()
        raise OverlappingBookingError()
    if count_active_bookings(db, user_id) >= MAX_ACTIVE_BOOKINGS:
        db.rollback()
        raise TooManyBookingsError()

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
