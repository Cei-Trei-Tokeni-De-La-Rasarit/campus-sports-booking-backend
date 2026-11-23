"""Modelul SQLAlchemy pentru tabelul facility_schedule."""

from datetime import time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FacilitySchedule(Base):
    """Programul unei facilități într-o zi a săptămânii (1 = luni, 7 = duminică).

    O zi fără rând în acest tabel înseamnă că facilitatea e închisă atunci.
    """

    __tablename__ = "facility_schedule"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="ck_schedule_weekday"),
        CheckConstraint("closes_at > opens_at", name="ck_schedule_closes_after"),
        UniqueConstraint("facility_id", "weekday", name="uq_schedule_day"),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facility.id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    opens_at: Mapped[time]
    closes_at: Mapped[time]
