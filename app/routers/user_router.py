"""Endpoint-urile API pentru administrarea utilizatorilor (/utilizatori)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import RoleUpdate, UserRead
from app.services import user_service

router = APIRouter(prefix="/utilizatori", tags=["Utilizatori"])


@router.put("/{user_id}/rol", response_model=UserRead)
def change_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserRead:
    """Schimbă rolul unui utilizator și facilitățile alocate (administrator).

    Pentru rolul manager, `facilitati_alocate` înlocuiește lista de acum.
    """
    try:
        user = user_service.change_role(db, admin, user_id, data)
    except user_service.UserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilizatorul nu există."
        ) from error
    except user_service.OwnRoleChangeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nu îți poți schimba propriul rol. "
            "Cere altui administrator să o facă.",
        ) from error
    except user_service.UnknownFacilitiesError as error:
        ids = ", ".join(str(facility_id) for facility_id in error.facility_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date invalide. facilitati_alocate: facilitățile {ids} nu există.",
        ) from error
    return UserRead.from_model(user)
