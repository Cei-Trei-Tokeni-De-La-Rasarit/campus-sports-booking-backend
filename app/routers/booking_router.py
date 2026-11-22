"""Endpoint-urile API pentru rezervări (/rezervari)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.booking import BookingCreate, BookingRead, BookingStatus
from app.services import booking_service, facility_service

router = APIRouter(prefix="/rezervari", tags=["Rezervări"])


@router.get("", response_model=list[BookingRead])
def list_bookings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    requested_status: Annotated[BookingStatus | None, Query(alias="stare")] = None,
) -> list[BookingRead]:
    """Întoarce rezervările utilizatorului autentificat."""
    now = facility_service.romania_now(db)
    bookings = booking_service.list_bookings(db, current_user.id, requested_status)
    return [
        BookingRead.from_model(booking, booking_service.public_status(booking, now))
        for booking in bookings
    ]


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookingRead:
    """Rezervă un slot liber pentru utilizatorul autentificat."""
    # Utilizatorul se ia din token, nu din datele trimise, ca nimeni să nu
    # poată rezerva în numele altcuiva.
    try:
        booking = booking_service.create_booking(db, current_user.id, data.slot_id)
    except booking_service.SlotNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Slotul nu există."
        ) from error
    except booking_service.FacilityNotBookableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Facilitatea nu poate fi rezervată acum.",
        ) from error
    except booking_service.SlotAlreadyStartedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slotul a început deja și nu mai poate fi rezervat.",
        ) from error
    except booking_service.OverlappingBookingError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ai deja o rezervare care se suprapune cu acest interval.",
        ) from error
    except booking_service.TooManyBookingsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Poți avea cel mult "
            f"{booking_service.MAX_ACTIVE_BOOKINGS} rezervări active.",
        ) from error
    except booking_service.SlotNotAvailableError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slotul nu mai este liber.",
        ) from error
    return BookingRead.from_model(booking)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Anulează o rezervare a utilizatorului autentificat."""
    try:
        booking_service.cancel_booking(db, current_user.id, booking_id)
    except booking_service.BookingNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rezervarea nu există."
        ) from error
    except booking_service.BookingAlreadyCancelledError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rezervarea este deja anulată.",
        ) from error
    except booking_service.CancellationTooLateError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rezervarea se poate anula cu cel puțin 24 de ore înainte "
            "de începutul intervalului.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
