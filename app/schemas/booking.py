"""Datele primite și trimise de API pentru rezervări.

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.booking import Booking
from app.schemas.time_slot import SlotRead

BookingStatus = Literal["confirmata", "anulata", "finalizata"]

# Valorile pentru stare din baza de date și echivalentul lor din API.
STATUS_FROM_DB: dict[str, str] = {
    "confirmed": "confirmata",
    "cancelled": "anulata",
}

# Cea mai mare valoare pe care o poate stoca o coloană INT din PostgreSQL;
# un id mai mare nu poate exista și ar da eroare în baza de date.
MAX_DB_ID = 2_147_483_647


class BookingCreate(BaseModel):
    """Datele trimise la rezervarea unui slot."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    # strict=True: se acceptă doar numere întregi, nu "12", 12.5 sau true.
    slot_id: int = Field(alias="slot_id", ge=1, le=MAX_DB_ID, strict=True)
    rules_accepted: bool = Field(alias="regulament_acceptat", strict=True)

    @field_validator("rules_accepted")
    @classmethod
    def rules_must_be_accepted(cls, accepted: bool) -> bool:
        """Rezervarea se face doar dacă regulamentul sălii a fost acceptat."""
        if not accepted:
            raise ValueError("Trebuie să accepți regulamentul sălii.")
        return accepted


class BookingRead(BaseModel):
    """O rezervare, așa cum este trimisă de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int = Field(alias="id")
    user_id: int = Field(alias="utilizator_id")
    slot: SlotRead = Field(alias="slot")
    created_at: datetime = Field(alias="data_crearii")
    status: BookingStatus = Field(alias="stare")

    @classmethod
    def from_model(cls, booking: Booking) -> "BookingRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            id=booking.id,
            user_id=booking.user_id,
            slot=SlotRead.from_model(booking.slot),
            created_at=booking.created_at,
            status=STATUS_FROM_DB[booking.status],
        )
