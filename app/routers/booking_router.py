"""Endpoint-urile API pentru rezervări (/rezervari)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.booking import BookingCreate, BookingRead
from app.services import booking_service

router = APIRouter(prefix="/rezervari", tags=["Rezervări"])


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
