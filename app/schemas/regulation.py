"""Datele regulamentului trimise de API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.regulation import Regulation


class RegulationRead(BaseModel):
    """Un regulament, așa cum este trimis de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    facility_id: int = Field(alias="facilitate_id")
    content: str = Field(alias="text")

    @classmethod
    def from_model(cls, regulation: Regulation) -> "RegulationRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            facility_id=regulation.facility_id,
            content=regulation.content,
        )
