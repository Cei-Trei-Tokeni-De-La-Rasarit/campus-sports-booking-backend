"""Modelul SQLAlchemy pentru tabelul time_slot."""

from datetime import date, time

from sqlalchemy import CheckConstraint, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimeSlot(Base):
    """Un interval din calendarul unei facilități (de exemplu, 10:00-11:00)."""

    __tablename__ = "time_slot"
    # Aceleași reguli ca în shemas.sql, ca modelul să descrie complet tabelul.
    __table_args__ = (
        CheckConstraint(
            "status IN ('free', 'booked', 'blocked')", name="ck_time_slot_status"
        ),
        CheckConstraint("end_time > start_time", name="ck_time_slot_end_after_start"),
        UniqueConstraint(
            "facility_id", "slot_date", "start_time", name="uq_time_slot_start"
        ),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    # Sloturile unei facilități se șterg odată cu ea (ON DELETE CASCADE).
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facility.id", ondelete="CASCADE")
    )
    slot_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    status: Mapped[str] = mapped_column(String(20), server_default="free")
