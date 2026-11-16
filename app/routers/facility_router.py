"""Endpoint-urile API pentru facilități (/facilitati)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin, require_manager_or_admin
from app.database import get_db
from app.models.facility import Facility
from app.models.user import User
from app.schemas.facility import FacilityData, FacilityFilters, FacilityRead
from app.schemas.time_slot import SlotRead
from app.services import facility_service, time_slot_service

router = APIRouter(prefix="/facilitati", tags=["Facilități"])


def get_existing_facility(facility_id: int, db: Session = Depends(get_db)) -> Facility:
    """Întoarce facilitatea cerută sau răspunde cu 404 dacă nu există."""
    facility = facility_service.get_facility(db, facility_id)
    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Facilitatea nu există."
        )
    return facility


@router.get("", response_model=list[FacilityRead])
def list_facilities(
    filters: Annotated[FacilityFilters, Query()], db: Session = Depends(get_db)
) -> list[FacilityRead]:
    """Catalogul facilităților active, cu filtre opționale."""
    facilities = facility_service.list_facilities(db, filters)
    return [FacilityRead.from_model(f) for f in facilities]


@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(
    facility: Facility = Depends(get_existing_facility),
) -> FacilityRead:
    """Detaliile unei facilități."""
    return FacilityRead.from_model(facility)


@router.post("", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(
    data: FacilityData,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> FacilityRead:
    """Adaugă o facilitate (doar administrator)."""
    return FacilityRead.from_model(facility_service.create_facility(db, data))


@router.put("/{facility_id}", response_model=FacilityRead)
def update_facility(
    data: FacilityData,
    facility: Facility = Depends(get_existing_facility),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
) -> FacilityRead:
    """Editează o facilitate (administrator sau manager)."""
    return FacilityRead.from_model(facility_service.update_facility(db, facility, data))


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility: Facility = Depends(get_existing_facility),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Șterge o facilitate care nu are intervale în calendar (doar administrator)."""
    try:
        facility_service.delete_facility(db, facility)
    except facility_service.FacilityHasSlotsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Facilitatea are intervale în calendar și nu poate fi ștearsă. "
            "Dezactiveaz-o cu status = inactiva.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{facility_id}/sloturi", response_model=list[SlotRead])
def list_facility_slots(
    start: date = Query(alias="de_la"),
    end: date = Query(alias="pana_la"),
    facility: Facility = Depends(get_existing_facility),
    db: Session = Depends(get_db),
) -> list[SlotRead]:
    """Calendarul unei facilități: sloturile dintre două date, cu starea lor."""
    try:
        slots = time_slot_service.list_slots(db, facility.id, start, end)
    except time_slot_service.InvalidPeriodError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date invalide. {error}",
        ) from error
    return [SlotRead.from_model(slot) for slot in slots]
