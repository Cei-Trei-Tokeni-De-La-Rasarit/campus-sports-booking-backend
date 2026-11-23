"""Modelul SQLAlchemy pentru tabelul facility_manager."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FacilityManager(Base):
    """O facilitate alocată unui manager de către administrator (KAN-94).

    Un manager poate edita doar facilitățile care apar aici pentru el.
    """

    __tablename__ = "facility_manager"

    # Cheia primară e perechea (manager, facilitate), ca în shemas.sql: aceeași
    # facilitate nu poate fi alocată de două ori aceluiași manager.
    manager_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facility.id", ondelete="CASCADE"), primary_key=True
    )
