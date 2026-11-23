"""Datele primite și trimise de API pentru notificări.

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.notification import Notification

NotificationType = Literal[
    "confirmare", "memento", "loc_eliberat", "mentenanta", "anulare", "reprogramare"
]

# Tipurile din baza de date și echivalentul lor din API.
TYPE_FROM_DB: dict[str, str] = {
    "confirmation": "confirmare",
    "reminder": "memento",
    "slot_released": "loc_eliberat",
    "maintenance": "mentenanta",
    "cancellation": "anulare",
    "reschedule": "reprogramare",
}


class NotificationUpdate(BaseModel):
    """Datele trimise la marcarea unei notificări ca citită (sau necitită)."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    # strict=True: se acceptă doar true sau false, nu "true" sau 1.
    is_read: bool = Field(alias="citita", strict=True)


class NotificationRead(BaseModel):
    """O notificare, așa cum este trimisă de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int = Field(alias="id")
    type: NotificationType = Field(alias="tip")
    message: str = Field(alias="mesaj")
    created_at: datetime = Field(alias="data")
    is_read: bool = Field(alias="citita")

    @classmethod
    def from_model(cls, notification: Notification) -> "NotificationRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            id=notification.id,
            type=TYPE_FROM_DB[notification.type],
            message=notification.message,
            # În bază e salvată în UTC, fără fus orar; îl adăugăm la răspuns.
            created_at=notification.created_at.replace(tzinfo=timezone.utc),
            is_read=notification.is_read,
        )
