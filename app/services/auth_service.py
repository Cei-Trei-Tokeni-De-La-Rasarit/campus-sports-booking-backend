"""Logica de business pentru înregistrare și autentificare."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRegister

ALLOWED_EMAIL_DOMAINS = ("@student.usv.ro", "@usv.ro")


class EmailAlreadyExistsError(Exception):
    """Aruncată când adresa de email este deja înregistrată."""


class InvalidCredentialsError(Exception):
    """Aruncată când email-ul sau parola sunt incorecte."""


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Caută un utilizator după ID."""
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Caută un utilizator după adresa de email."""
    stmt = select(User).where(User.email == email.lower().strip())
    return db.scalar(stmt)


def register_user(db: Session, data: UserRegister) -> User:
    """Creează un cont nou cu rol implicit 'user'."""
    normalized_email = data.email.lower().strip()

    if not normalized_email.endswith(ALLOWED_EMAIL_DOMAINS):
        raise InvalidInstitutionalEmailError()

    if get_user_by_email(db, normalized_email) is not None:
        raise EmailAlreadyExistsError()

    user = User(
        name=data.name.strip(),
        email=normalized_email,
        password_hash=hash_password(data.password),
        role="user",
        email_notifications=data.email_notifications,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verifică credențialele și întoarce utilizatorul dacă sunt valide."""
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return user