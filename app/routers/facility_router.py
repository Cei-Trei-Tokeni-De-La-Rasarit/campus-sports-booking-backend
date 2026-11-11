"""Endpoint-urile API pentru facilități (/facilitati)."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.facility import Facility
from app.schemas.facility import FacilityData, FacilityRead
from app.services import facility_service

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
def list_facilities(db: Session = Depends(get_db)) -> list[FacilityRead]:
    """Catalogul facilităților."""
    return [FacilityRead.from_model(f) for f in facility_service.list_facilities(db)]


@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(
    facility: Facility = Depends(get_existing_facility),
) -> FacilityRead:
    """Detaliile unei facilități."""
    return FacilityRead.from_model(facility)


@router.post("", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(data: FacilityData, db: Session = Depends(get_db)) -> FacilityRead:
    """Adaugă o facilitate."""
    return FacilityRead.from_model(facility_service.create_facility(db, data))


@router.put("/{facility_id}", response_model=FacilityRead)
def update_facility(
    data: FacilityData,
    facility: Facility = Depends(get_existing_facility),
    db: Session = Depends(get_db),
) -> FacilityRead:
    """Editează o facilitate (pentru dezactivare se trimite status = inactiva)."""
    return FacilityRead.from_model(facility_service.update_facility(db, facility, data))


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility: Facility = Depends(get_existing_facility),
    db: Session = Depends(get_db),
) -> Response:
    """Șterge o facilitate care nu are intervale în calendar."""
    try:
        facility_service.delete_facility(db, facility)
    except facility_service.FacilityHasSlotsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Facilitatea are intervale în calendar și nu poate fi ștearsă. "
            "Dezactiveaz-o cu status = inactiva.",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
