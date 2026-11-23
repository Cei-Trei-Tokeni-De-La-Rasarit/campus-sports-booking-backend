"""Logica aplicației pentru rezervări."""

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.facility import Facility
from app.models.time_slot import TimeSlot
from app.models.user import User
from app.services import facility_service, notification_service

# Câte rezervări care nu au început încă poate avea un utilizator odată,
# ca un singur cont să nu poată ocupa tot calendarul.
MAX_ACTIVE_BOOKINGS = 3

# Cu cât timp înainte de începutul intervalului se mai poate anula o
# rezervare (decizia din 22.11.2026), ca slotul să poată fi luat de altcineva.
CANCELLATION_NOTICE = timedelta(hours=24)


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


class BookingNotFoundError(Exception):
    """Rezervarea nu există sau este a altui utilizator."""


class BookingAlreadyCancelledError(Exception):
    """Rezervarea este deja anulată."""


class CancellationTooLateError(Exception):
    """Au rămas mai puțin de 24 de ore până la începutul intervalului."""


class SameSlotError(Exception):
    """Reprogramarea cere același interval pe care e deja rezervarea."""


class OtherFacilitySlotError(Exception):
    """Intervalul nou este al altei săli decât rezervarea."""


def public_status(booking: Booking, now: datetime) -> str:
    """Calculează starea afișată a unei rezervări."""
    if booking.status == "cancelled":
        return "anulata"
    if (booking.slot.slot_date, booking.slot.end_time) <= (now.date(), now.time()):
        return "finalizata"
    return "confirmata"


def list_bookings(
    db: Session, user_id: int, requested_status: str | None = None
) -> list[Booking]:
    """Întoarce rezervările utilizatorului, ordonate după slot."""
    bookings = list(
        db.scalars(
            select(Booking)
            .join(TimeSlot, Booking.slot_id == TimeSlot.id)
            .where(Booking.user_id == user_id)
            .order_by(TimeSlot.slot_date, TimeSlot.start_time)
        )
    )
    if requested_status is None:
        return bookings

    now = facility_service.romania_now(db)
    return [
        booking
        for booking in bookings
        if public_status(booking, now) == requested_status
    ]


def has_started(db: Session, slot: TimeSlot) -> bool:
    """Spune dacă slotul a început deja, după ora României."""
    now = facility_service.romania_now(db)
    return (slot.slot_date, slot.start_time) <= (now.date(), now.time())


def has_overlapping_booking(
    db: Session, user_id: int, slot: TimeSlot, ignored_booking_id: int | None = None
) -> bool:
    """Spune dacă utilizatorul are o rezervare confirmată în același interval.

    Două intervale din aceeași zi se suprapun dacă fiecare începe înainte să
    se termine celălalt (10:00-11:00 și 11:00-12:00 nu se suprapun). La
    reprogramare, rezervarea mutată nu se socotește (`ignored_booking_id`):
    altfel 10:00-12:00 nu s-ar putea muta pe 11:00-13:00.
    """
    query = (
        select(Booking.id)
        .join(TimeSlot, Booking.slot_id == TimeSlot.id)
        .where(
            Booking.user_id == user_id,
            Booking.status == "confirmed",
            Booking.id != ignored_booking_id,
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
    facility = db.get(Facility, slot.facility_id)
    if facility.status != "active":
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
    notification_service.add_notification(
        db,
        user_id,
        "confirmation",
        notification_service.describe_slot(facility, slot),
    )
    try:
        db.commit()
    except IntegrityError as error:
        # A doua protecție: indexul unic permite o singură rezervare
        # confirmată pe slot.
        db.rollback()
        raise SlotNotAvailableError() from error
    db.refresh(booking)
    return booking


def can_be_cancelled(slot: TimeSlot, now: datetime) -> bool:
    """Spune dacă mai sunt cel puțin 24 de ore până la începutul slotului."""
    starts_at = datetime.combine(slot.slot_date, slot.start_time)
    return starts_at - now >= CANCELLATION_NOTICE


def cancel_booking(db: Session, user_id: int, booking_id: int) -> None:
    """Anulează rezervarea utilizatorului; slotul redevine liber.

    Ridică BookingNotFoundError, BookingAlreadyCancelledError sau
    CancellationTooLateError dacă rezervarea nu se poate anula.
    """
    # Un id în afara intervalului coloanei INT nu poate exista; fără această
    # verificare, PostgreSQL ar da eroare (500).
    if not 1 <= booking_id <= facility_service.MAX_DB_ID:
        raise BookingNotFoundError()
    booking = db.get(Booking, booking_id)
    # Rezervarea altcuiva primește același răspuns ca una inexistentă, ca
    # nimeni să nu poată afla ce rezervări au ceilalți.
    if booking is None or booking.user_id != user_id:
        raise BookingNotFoundError()
    if booking.status == "cancelled":
        raise BookingAlreadyCancelledError()
    if not can_be_cancelled(booking.slot, facility_service.romania_now(db)):
        raise CancellationTooLateError()

    # Blocăm întâi rândul utilizatorului, ca la creare și la reprogramare:
    # o anulare și o reprogramare trimise în același timp se execută pe rând,
    # în aceeași ordine a blocărilor (altfel PostgreSQL ar găsi un deadlock).
    db.execute(select(User.id).where(User.id == user_id).with_for_update())

    # Anulăm cu o singură comandă, care schimbă rezervarea doar dacă e încă
    # confirmată. Dacă două anulări vin în același timp, a doua nu mai găsește
    # rezervarea confirmată (0 rânduri modificate). RETURNING dă intervalul
    # pe care e rezervarea chiar acum: dacă o reprogramare a mutat-o între
    # timp, eliberăm intervalul nou, nu pe cel citit mai devreme.
    slot_id = db.scalar(
        update(Booking)
        .where(Booking.id == booking_id, Booking.status == "confirmed")
        .values(status="cancelled")
        .returning(Booking.slot_id)
    )
    if slot_id is None:
        db.rollback()
        raise BookingAlreadyCancelledError()

    # Slotul redevine liber doar dacă era rezervat; unul blocat pentru
    # mentenanță rămâne blocat.
    db.execute(
        update(TimeSlot)
        .where(TimeSlot.id == slot_id, TimeSlot.status == "booked")
        .values(status="free")
    )
    slot = db.get(TimeSlot, slot_id, populate_existing=True)
    notification_service.add_notification(
        db,
        user_id,
        "cancellation",
        notification_service.describe_slot(db.get(Facility, slot.facility_id), slot),
    )
    db.commit()


def reschedule_booking(
    db: Session, user_id: int, booking_id: int, new_slot_id: int
) -> Booking:
    """Mută o rezervare confirmată pe alt interval liber din aceeași sală.

    Rezervarea veche trebuie să se mai poată anula (24 de ore), iar intervalul
    nou respectă regulile de la creare. Totul se face într-o tranzacție:
    intervalul nou devine ocupat, cel vechi liber, iar rezervarea rămâne
    aceeași (același id), cu alt interval.

    Ridică BookingNotFoundError, BookingAlreadyCancelledError,
    CancellationTooLateError, SameSlotError, SlotNotFoundError,
    OtherFacilitySlotError, FacilityNotBookableError, SlotAlreadyStartedError,
    OverlappingBookingError sau SlotNotAvailableError.
    """
    # Aceleași verificări ca la anulare: reprogramarea e o anulare urmată de
    # o rezervare nouă, deci are aceeași regulă de 24 de ore.
    if not 1 <= booking_id <= facility_service.MAX_DB_ID:
        raise BookingNotFoundError()
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != user_id:
        raise BookingNotFoundError()
    if booking.status == "cancelled":
        raise BookingAlreadyCancelledError()
    old_slot = booking.slot
    if not can_be_cancelled(old_slot, facility_service.romania_now(db)):
        raise CancellationTooLateError()

    if new_slot_id == old_slot.id:
        raise SameSlotError()
    new_slot = db.get(TimeSlot, new_slot_id)
    if new_slot is None:
        raise SlotNotFoundError()
    if new_slot.facility_id != old_slot.facility_id:
        raise OtherFacilitySlotError()
    facility = db.get(Facility, new_slot.facility_id)
    if facility.status != "active":
        raise FacilityNotBookableError()
    if has_started(db, new_slot):
        raise SlotAlreadyStartedError()

    # Ca la creare: rândul utilizatorului blocat, ca două cereri ale aceluiași
    # cont să se verifice pe rând. Numărul de rezervări active nu se schimbă
    # (mutăm una existentă), deci maximul nu se mai verifică.
    db.execute(select(User.id).where(User.id == user_id).with_for_update())
    if has_overlapping_booking(db, user_id, new_slot, ignored_booking_id=booking.id):
        db.rollback()
        raise OverlappingBookingError()

    # Ocupăm intervalul nou doar dacă e încă liber (cereri simultane).
    taken = db.execute(
        update(TimeSlot)
        .where(TimeSlot.id == new_slot.id, TimeSlot.status == "free")
        .values(status="booked")
    )
    if taken.rowcount == 0:
        db.rollback()
        raise SlotNotAvailableError()

    # Mutăm rezervarea doar dacă e încă confirmată și tot pe intervalul vechi:
    # o anulare sau o altă reprogramare trimisă în același timp o oprește.
    moved = db.execute(
        update(Booking)
        .where(
            Booking.id == booking.id,
            Booking.status == "confirmed",
            Booking.slot_id == old_slot.id,
        )
        .values(slot_id=new_slot.id)
    )
    if moved.rowcount == 0:
        db.rollback()
        raise BookingAlreadyCancelledError()

    # Intervalul vechi redevine liber (unul blocat pentru mentenanță rămâne).
    db.execute(
        update(TimeSlot)
        .where(TimeSlot.id == old_slot.id, TimeSlot.status == "booked")
        .values(status="free")
    )
    notification_service.add_notification(
        db,
        user_id,
        "reschedule",
        notification_service.describe_slot(facility, old_slot)
        + " → "
        + notification_service.describe_slot(facility, new_slot),
    )
    try:
        db.commit()
    except IntegrityError as error:
        # A doua protecție: indexul unic permite o singură rezervare
        # confirmată pe interval.
        db.rollback()
        raise SlotNotAvailableError() from error
    db.refresh(booking)
    return booking
