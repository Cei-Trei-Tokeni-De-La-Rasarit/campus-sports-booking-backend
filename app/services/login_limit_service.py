"""Limita de încercări greșite la autentificare (KAN-127).

Fără limită, parola unui cont se poate ghici încercând mii de parole la rând
(atac de tip brute force). Regula:
- după MAX_FAILED_ATTEMPTS încercări greșite în ATTEMPT_WINDOW pentru același
  email, autentificarea e refuzată (429) până expiră cea mai veche încercare;
- încercările făcute cât emailul e blocat nu se numără, ca un atacator să nu
  poată ține contul altcuiva blocat la nesfârșit;
- limita se aplică la fel și emailurilor fără cont, ca răspunsul să nu arate
  ce conturi există;
- o autentificare reușită șterge încercările greșite.
"""

import math
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.login_attempt import LoginAttempt

MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW = timedelta(minutes=15)


class TooManyAttemptsError(Exception):
    """Prea multe încercări greșite; `retry_after` = secunde de așteptat."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(retry_after)
        self.retry_after = retry_after


def database_now(db: Session) -> datetime:
    """Ora de acum, de la PostgreSQL (aceeași pentru toate serverele)."""
    return db.scalar(select(func.now()))


def lock_email(db: Session, email: str) -> None:
    """Încercările pentru același email se execută pe rând, până la commit.

    Fără lacăt, mai multe cereri trimise în același moment ar trece toate de
    verificarea limitei înainte ca vreuna să fie salvată. Lacătul PostgreSQL
    (advisory lock) funcționează și pentru emailurile fără cont, care nu au
    un rând de blocat în tabelul utilizatorilor.
    """
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(email))))


def check_not_blocked(db: Session, email: str, now: datetime) -> None:
    """Ridică TooManyAttemptsError dacă emailul are prea multe încercări."""
    window_start = now - ATTEMPT_WINDOW
    # Încercările mai vechi decât fereastra nu mai contează; le ștergem, ca
    # tabelul să rămână mic.
    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.email == email, LoginAttempt.created_at <= window_start
        )
    )
    failures = list(
        db.scalars(
            select(LoginAttempt.created_at)
            .where(LoginAttempt.email == email)
            .order_by(LoginAttempt.created_at)
        )
    )
    if len(failures) >= MAX_FAILED_ATTEMPTS:
        # Emailul se deblochează când iese din fereastră încercarea care îl
        # ține la limită.
        unblocked_at = failures[len(failures) - MAX_FAILED_ATTEMPTS] + ATTEMPT_WINDOW
        retry_after = max(1, math.ceil((unblocked_at - now).total_seconds()))
        db.commit()
        raise TooManyAttemptsError(retry_after)


def record_failure(db: Session, email: str, now: datetime) -> None:
    """Salvează o încercare greșită."""
    db.add(LoginAttempt(email=email, created_at=now))
    db.commit()


def clear_failures(db: Session, email: str) -> None:
    """Șterge încercările greșite după o autentificare reușită."""
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
    db.commit()
