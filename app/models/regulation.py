"""Modelul SQLAlchemy pentru tabelul regulation."""

from sqlalchemy import ForeignKey, Identity, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Regulation(Base):
    """Regulamentul unei facilități."""

    __tablename__ = "regulation"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facility.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
