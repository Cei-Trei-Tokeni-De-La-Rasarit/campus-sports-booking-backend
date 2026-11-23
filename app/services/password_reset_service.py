"""Logica aplicației pentru resetarea parolei prin email (KAN-111).

Pașii: utilizatorul cere un link (`request_reset`), primește pe email un
token aleatoriu, iar cu el își alege o parolă nouă (`confirm_reset`). În baza
de date se păstrează doar hash-ul SHA-256 al token-ului.
"""

import hashlib
import logging
import os
import secrets
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services import auth_service, email_service

logger = logging.getLogger(__name__)

# Cât timp e valabil un link de resetare.
TOKEN_LIFETIME = timedelta(minutes=30)
# Câte linkuri se pot cere pentru același cont într-o oră.
MAX_REQUESTS_PER_HOUR = 3
# Adresa frontend-ului, pentru linkul din email (fără „/” la sfârșit).
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

EMAIL_SUBJECT = "Resetarea parolei - Campus Sports Booking"
EMAIL_BODY = """Bună, {name}!

Am primit o cerere pentru resetarea parolei contului tău Campus Sports Booking.
Ca să alegi o parolă nouă, deschide linkul de mai jos în următoarele 30 de minute:

{link}

Linkul poate fi folosit o singură dată. Dacă nu tu ai cerut resetarea, ignoră
acest email; parola ta rămâne neschimbată.
"""


class InvalidResetTokenError(Exception):
    """Token-ul nu există, a expirat sau a fost deja folosit."""


def hash_token(token: str) -> str:
    """Hash-ul SHA-256 (hexazecimal) al token-ului din link."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_reset(db: Session, email: str) -> tuple[str, str] | None:
    """Creează un token de resetare pentru contul cu adresa dată.

    Întoarce (adresa, textul emailului) de trimis sau None, dacă nu există
    cont sau dacă s-au cerut deja MAX_REQUESTS_PER_HOUR linkuri în ultima oră.
    Răspunsul API e același în toate cazurile, ca să nu se afle ce conturi există.
    """
    user = auth_service.get_user_by_email(db, email)
    if user is None:
        return None
    # Blocăm rândul utilizatorului: cereri trimise în același timp se numără
    # pe rând, deci limita pe oră nu poate fi depășită.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    recent = db.scalar(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at > func.now() - timedelta(hours=1),
        )
    )
    if recent >= MAX_REQUESTS_PER_HOUR:
        db.rollback()
        logger.info("Limita de resetări pe oră atinsă pentru utilizatorul %s.", user.id)
        return None

    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            # Timpul vine din baza de date, ca la verificarea din confirm_reset.
            expires_at=func.now() + TOKEN_LIFETIME,
        )
    )
    db.commit()
    link = f"{FRONTEND_URL}/parola-noua?token={token}"
    return user.email, EMAIL_BODY.format(name=user.name, link=link)


def send_reset_email(to: str, body: str) -> None:
    """Trimite emailul cu linkul; o eroare se scrie doar în log.

    Rulează după ce răspunsul a plecat (BackgroundTasks), deci utilizatorul
    primește oricum același răspuns.
    """
    try:
        email_service.send_email(to, EMAIL_SUBJECT, body)
    except email_service.EmailSendError:
        logger.warning("Emailul pentru resetarea parolei nu a fost trimis.")


def confirm_reset(db: Session, token: str, new_password: str) -> None:
    """Schimbă parola cu un token valid și invalidează toate token-urile contului.

    Ridică InvalidResetTokenError dacă token-ul nu există, a expirat sau a fost
    deja folosit.
    """
    # FOR UPDATE: două confirmări simultane cu același token se fac pe rând,
    # iar a doua îl găsește deja folosit.
    reset_token = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(token),
            PasswordResetToken.used.is_(False),
            PasswordResetToken.expires_at > func.now(),
        )
        .with_for_update()
    )
    if reset_token is None:
        raise InvalidResetTokenError
    user = db.get(User, reset_token.user_id)
    if user is None:
        raise InvalidResetTokenError
    user.password_hash = hash_password(new_password)
    # Toate linkurile contului devin invalide, inclusiv cel folosit acum.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used.is_(False),
        )
        .values(used=True)
    )
    db.commit()
