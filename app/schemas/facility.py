"""Datele primite și trimise de API pentru facilități.

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.facility import Facility

FacilityStatus = Literal["activa", "mentenanta", "inactiva"]

# Valorile pentru status din API și echivalentul lor din baza de date.
STATUS_TO_DB: dict[str, str] = {
    "activa": "active",
    "mentenanta": "under_maintenance",
    "inactiva": "inactive",
}
STATUS_FROM_DB: dict[str, str] = {
    db_value: api_value for api_value, db_value in STATUS_TO_DB.items()
}


class FacilityData(BaseModel):
    """Datele unei facilități, primite la creare și la editare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    name: str = Field(alias="nume", min_length=1, max_length=100)
    sport: str = Field(alias="sport", min_length=1, max_length=50)
    location: str = Field(alias="locatie", min_length=1, max_length=150)
    capacity: int = Field(alias="capacitate", ge=1)
    schedule: str | None = Field(default=None, alias="program", max_length=200)
    status: FacilityStatus = Field(default="activa", alias="status")

    def to_db_values(self) -> dict[str, str | int | None]:
        """Întoarce valorile pentru coloanele tabelului facility."""
        values = self.model_dump()
        values["status"] = STATUS_TO_DB[self.status]
        return values


class FacilityRead(FacilityData):
    """O facilitate, așa cum este trimisă de API."""

    id: int = Field(alias="id")

    @classmethod
    def from_model(cls, facility: Facility) -> "FacilityRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            id=facility.id,
            name=facility.name,
            sport=facility.sport,
            location=facility.location,
            capacity=facility.capacity,
            schedule=facility.schedule,
            status=STATUS_FROM_DB[facility.status],
        )
