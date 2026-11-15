"""Modelul SQLAlchemy pentru tabelul user."""

from sqlalchemy import Boolean, CheckConstraint, Identity, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """Un utilizator al platformei (student, administrator sau manager)."""

    __tablename__ = "user"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'administrator', 'manager')",
            name="ck_user_role",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="user")
    email_notifications: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE")
    )
