"""Datele primite și trimise de API pentru programul unei facilități.

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.facility_schedule import FacilitySchedule

# Duratele permise pentru un interval din calendar, în minute.
SlotMinutes = Literal[60, 90, 120]


def minutes_of_day(moment: time) -> int:
    """Câte minute au trecut de la miezul nopții (08:30 înseamnă 510)."""
    return moment.hour * 60 + moment.minute


class ScheduleDay(BaseModel):
    """Programul dintr-o zi a săptămânii (1 = luni, 7 = duminică)."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    # strict=True: se acceptă doar numere întregi, nu "1" sau 1.0.
    weekday: int = Field(alias="zi", ge=1, le=7, strict=True)
    opens_at: time = Field(alias="deschidere")
    closes_at: time = Field(alias="inchidere")

    @field_validator("opens_at", "closes_at")
    @classmethod
    def whole_minutes(cls, value: time) -> time:
        """Orele se dau la minut („08:30”), fără secunde și fără fus orar."""
        if value.second or value.microsecond or value.tzinfo:
            raise ValueError("Ora trebuie să fie în formatul HH:MM.")
        return value

    @model_validator(mode="after")
    def closes_after_opening(self) -> "ScheduleDay":
        """Ora de închidere trebuie să fie după cea de deschidere."""
        if self.closes_at <= self.opens_at:
            raise ValueError("Ora de închidere trebuie să fie după ora de deschidere.")
        return self


class ScheduleData(BaseModel):
    """Programul unei facilități, primit la `PUT /facilitati/{id}/program`."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    slot_minutes: SlotMinutes = Field(alias="durata_slot")
    # O zi care lipsește din listă înseamnă că sala e închisă atunci.
    days: list[ScheduleDay] = Field(alias="zile", max_length=7)

    @model_validator(mode="after")
    def check_days(self) -> "ScheduleData":
        """Fiecare zi apare o singură dată și se împarte exact în intervale."""
        weekdays = [day.weekday for day in self.days]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Fiecare zi poate apărea o singură dată în program.")
        for day in self.days:
            length = minutes_of_day(day.closes_at) - minutes_of_day(day.opens_at)
            if length % self.slot_minutes:
                raise ValueError(
                    f"Programul din ziua {day.weekday} nu se împarte exact în "
                    f"intervale de {self.slot_minutes} de minute."
                )
        return self


class ScheduleDayRead(BaseModel):
    """O zi din program, așa cum este trimisă de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    weekday: int = Field(alias="zi")
    opens_at: str = Field(alias="deschidere")
    closes_at: str = Field(alias="inchidere")

    @classmethod
    def from_model(cls, day: FacilitySchedule) -> "ScheduleDayRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            weekday=day.weekday,
            opens_at=day.opens_at.strftime("%H:%M"),
            closes_at=day.closes_at.strftime("%H:%M"),
        )


class ScheduleRead(BaseModel):
    """Programul unei facilități, așa cum este trimis de API."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    slot_minutes: int = Field(alias="durata_slot")
    days: list[ScheduleDayRead] = Field(alias="zile")


class ScheduleUpdateRead(ScheduleRead):
    """Răspunsul la schimbarea programului.

    Rezervările viitoare din afara noului program nu se anulează automat;
    numărul lor îi spune managerului câte trebuie rezolvate.
    """

    bookings_outside: int = Field(alias="rezervari_in_afara_programului")
