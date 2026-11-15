"""Endpoint-urile API pentru autentificare (/auth)."""

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserLogin, UserRead, UserRegister
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Utilizatori"])
users_router = APIRouter(prefix="/utilizatori", tags=["Utilizatori"])
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extrage și validează utilizatorul curent din header-ul Authorization."""
    unauthorized_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalid sau expirat.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Lipsește token-ul de autentificare.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise unauthorized_exc
        user_id = int(user_id_str)
    except (jwt.PyJWTError, ValueError) as error:
        raise unauthorized_exc from error

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise unauthorized_exc
    return user


@router.post(
    "/inregistrare",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def sign_up(data: UserRegister, db: Session = Depends(get_db)) -> UserRead:
    """Creează un cont nou, cu rolul client."""
    try:
        user = auth_service.register_user(db, data)
    except auth_service.EmailAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Există deja un cont înregistrat cu această adresă de email.",
        ) from error

    return UserRead.from_model(user)


@router.post("/autentificare", response_model=TokenResponse)
def sign_in(data: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Autentifică utilizatorul și returnează token-ul JWT."""
    try:
        user = auth_service.authenticate_user(db, data.email, data.password)
    except auth_service.InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorectă.",
        ) from error

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(token=token, user=UserRead.from_model(user))


@users_router.get("/eu", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Returnează profilul utilizatorului autentificat curent."""
    return UserRead.from_model(current_user)
