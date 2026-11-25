"""Modelul SQLAlchemy pentru tabelul login_attempt."""

from datetime import datetime

from sqlalchemy import DateTime, Identity, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoginAttempt(Base):
    """O încercare de autentificare eșuată (KAN-127).

    Se păstrează după email, nu după utilizator, ca limita să se aplice la fel
    și adreselor fără cont: răspunsul nu arată ce conturi există.
    """

    __tablename__ = "login_attempt"
    # Același index ca în shemas.sql: încercările unui email, în ordinea lor.
    __table_args__ = (Index("ix_login_attempt_email", "email", "created_at"),)

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
