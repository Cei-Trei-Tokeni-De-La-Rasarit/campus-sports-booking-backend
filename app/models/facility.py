"""Modelul SQLAlchemy pentru tabelul facility."""

from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Facility(Base):
    """O facilitate sportivă (sală, teren, bazin) din campus."""

    __tablename__ = "facility"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sport: Mapped[str] = mapped_column(String(50))
    location: Mapped[str] = mapped_column(String(150))
    capacity: Mapped[int]
    schedule: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), server_default="active")
