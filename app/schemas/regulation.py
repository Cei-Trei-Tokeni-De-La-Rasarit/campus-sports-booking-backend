"""Datele regulamentului primite și trimise de API."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.regulation import Regulation

# Lungimea maximă a textului unui regulament (KAN-110).
MAX_REGULATION_LENGTH = 5000


class RegulationData(BaseModel):
    """Regulamentul primit la `PUT /facilitati/{id}/regulament`."""

    # str_strip_whitespace elimină spațiile de la capete înainte de verificări,
    # așa că un text format doar din spații devine gol și e respins.
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, str_strip_whitespace=True
    )

    content: str = Field(alias="text", min_length=1, max_length=MAX_REGULATION_LENGTH)


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
