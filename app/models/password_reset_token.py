"""Modelul SQLAlchemy pentru tabelul password_reset_token."""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PasswordResetToken(Base):
    """Un link de resetare a parolei, trimis pe email (KAN-111).

    Se păstrează doar hash-ul token-ului: cine citește baza de date nu poate
    folosi linkurile trimise.
    """

    __tablename__ = "password_reset_token"
    # Aceleași reguli ca în shemas.sql, ca modelul să descrie complet tabelul.
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_reset_token_expires"),
        Index("ix_password_reset_token_user", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    # SHA-256 în hexazecimal: întotdeauna 64 de caractere.
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"))
