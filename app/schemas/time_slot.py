"""Datele trimise de API pentru intervalele din calendar (sloturi).

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.time_slot import TimeSlot

SlotStatus = Literal["liber", "rezervat", "blocat"]

# Valorile pentru stare din baza de date și echivalentul lor din API.
STATUS_FROM_DB: dict[str, str] = {
    "free": "liber",
    "booked": "rezervat",
    "blocked": "blocat",
}


class SlotRead(BaseModel):
    """Un interval din calendar, așa cum este trimis de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int = Field(alias="id")
    facility_id: int = Field(alias="facilitate_id")
    slot_date: date = Field(alias="data")
    # Orele se trimit ca text „HH:MM”, ca în specificație.
    start_time: str = Field(alias="ora_start")
    end_time: str = Field(alias="ora_sfarsit")
    status: SlotStatus = Field(alias="stare")

    @classmethod
    def from_model(cls, slot: TimeSlot) -> "SlotRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            id=slot.id,
            facility_id=slot.facility_id,
            slot_date=slot.slot_date,
            start_time=slot.start_time.strftime("%H:%M"),
            end_time=slot.end_time.strftime("%H:%M"),
            status=STATUS_FROM_DB[slot.status],
        )
