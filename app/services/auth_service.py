"""Logica de business pentru înregistrarea utilizatorilor."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserRegister


class EmailAlreadyExistsError(Exception):
    """Aruncată când adresa de email este deja înregistrată."""


def get_user_by_email(db: Session, email: str) -> User | None:
    """Caută un utilizator după adresa de email."""
    stmt = select(User).where(User.email == email.lower().strip())
    return db.scalar(stmt)


def register_user(db: Session, data: UserRegister) -> User:
    """Creează un cont nou cu rol implicit 'user'."""
    normalized_email = data.email.lower().strip()
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
    try:
        db.commit()
    except IntegrityError as error:
        # Două cereri simultane cu același email: a doua e oprită de UNIQUE.
        db.rollback()
        raise EmailAlreadyExistsError() from error
    db.refresh(user)
    return user
