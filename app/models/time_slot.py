"""Modelul SQLAlchemy pentru tabelul time_slot."""

from datetime import date, time

from sqlalchemy import ForeignKey, Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimeSlot(Base):
    """Un interval din calendarul unei facilități (de exemplu, 10:00-11:00)."""

    __tablename__ = "time_slot"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facility.id"))
    slot_date: Mapped[date]
    start_time: Mapped[time]
    end_time: Mapped[time]
    status: Mapped[str] = mapped_column(String(20), server_default="free")
