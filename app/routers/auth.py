"""Endpoint-urile API pentru autentificare (/auth)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import UserRead, UserRegister
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autentificare"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def sign_up(data: UserRegister, db: Session = Depends(get_db)) -> UserRead:
    """Înregistrează un utilizator nou."""
    try:
        user = auth_service.register_user(db, data)
    except auth_service.EmailAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Există deja un cont înregistrat cu această adresă de email.",
        ) from error

    return UserRead.from_model(user)