"""Modelul SQLAlchemy pentru tabelul booking."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.time_slot import TimeSlot


class Booking(Base):
    """Rezervarea unui interval din calendar de către un utilizator."""

    __tablename__ = "booking"
    # Aceleași reguli ca în shemas.sql, ca modelul să descrie complet tabelul.
    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed', 'cancelled')", name="ck_booking_status"
        ),
        # Un slot poate avea o singură rezervare confirmată (fără dublă rezervare).
        Index(
            "uq_booking_active_slot",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("time_slot.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), server_default="confirmed")

    # Slotul rezervat, ca răspunsul să-l poată include complet.
    slot: Mapped[TimeSlot] = relationship()
