"""Logica aplicației pentru programul pe zile al unei facilități.

Din program se generează intervalele din calendar: de exemplu, o sală
deschisă luni 08:00-12:00, cu intervale de 120 de minute, are luni intervalele
08:00-10:00 și 10:00-12:00.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.facility import Facility
from app.models.facility_schedule import FacilitySchedule
from app.models.time_slot import TimeSlot
from app.schemas.schedule import ScheduleData
from app.services import facility_service

# Până la câte zile în viitor se generează intervale. Fără limită, oricine ar
# putea umple baza cerând calendarul pentru anii următori.
GENERATION_HORIZON_DAYS = 56


def get_schedule(db: Session, facility_id: int) -> list[FacilitySchedule]:
    """Programul facilității, în ordinea zilelor (luni prima)."""
    return list(
        db.scalars(
            select(FacilitySchedule)
            .where(FacilitySchedule.facility_id == facility_id)
            .order_by(FacilitySchedule.weekday)
        )
    )


def day_slots(day: FacilitySchedule, slot_minutes: int) -> list[tuple[time, time]]:
    """Intervalele (început, sfârșit) dintr-o zi a programului."""
    start = datetime.combine(date.min, day.opens_at)
    closes = datetime.combine(date.min, day.closes_at)
    step = timedelta(minutes=slot_minutes)
    slots = []
    while start + step <= closes:
        slots.append((start.time(), (start + step).time()))
        start += step
    return slots


def fits_schedule(
    slot: TimeSlot, schedule: dict[int, FacilitySchedule], slot_minutes: int
) -> bool:
    """Spune dacă intervalul este unul dintre cele generate de program."""
    day = schedule.get(slot.slot_date.isoweekday())
    if day is None:
        return False
    return (slot.start_time, slot.end_time) in day_slots(day, slot_minutes)


def overlaps(slot: TimeSlot, start: time, end: time) -> bool:
    """Spune dacă intervalul existent se suprapune cu [start, end)."""
    return slot.start_time < end and slot.end_time > start


def generate_slots(db: Session, facility: Facility, start: date, end: date) -> None:
    """Adaugă în calendar intervalele din program care lipsesc în perioada dată.

    Se generează doar pentru zilele de azi încolo, cel mult până la
    GENERATION_HORIZON_DAYS. Un interval nou nu se adaugă dacă s-ar suprapune
    cu unul existent (de exemplu, o rezervare de 2 ore păstrată după ce
    durata a devenit 1 oră).
    """
    # O sală inactivă nu se mai rezervă, deci nu-i mai adăugăm intervale.
    if facility.status == "inactive":
        return
    # Blocare partajată pe rândul sălii: o schimbare de program trimisă în
    # același timp (care blochează rândul exclusiv) așteaptă generarea, iar
    # generarea așteaptă schimbarea. Altfel s-ar putea genera intervale după
    # programul vechi, imediat după ce acesta a fost înlocuit.
    db.execute(
        select(Facility.id).where(Facility.id == facility.id).with_for_update(read=True)
    )
    schedule = {day.weekday: day for day in get_schedule(db, facility.id)}
    if not schedule:
        return
    today = facility_service.romania_now(db).date()
    first = max(start, today)
    last = min(end, today + timedelta(days=GENERATION_HORIZON_DAYS))
    if first > last:
        return

    existing = db.scalars(
        select(TimeSlot).where(
            TimeSlot.facility_id == facility.id,
            TimeSlot.slot_date >= first,
            TimeSlot.slot_date <= last,
        )
    ).all()
    rows = []
    current = first
    while current <= last:
        day = schedule.get(current.isoweekday())
        if day is not None:
            same_day = [slot for slot in existing if slot.slot_date == current]
            for slot_start, slot_end in day_slots(day, facility.slot_minutes):
                if not any(overlaps(slot, slot_start, slot_end) for slot in same_day):
                    rows.append(
                        {
                            "facility_id": facility.id,
                            "slot_date": current,
                            "start_time": slot_start,
                            "end_time": slot_end,
                        }
                    )
        current += timedelta(days=1)
    if not rows:
        return

    # ON CONFLICT DO NOTHING: dacă două cereri generează aceeași zi în același
    # timp, a doua nu mai adaugă nimic (cheia unică pe sală, zi și oră).
    db.execute(
        insert(TimeSlot)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=["facility_id", "slot_date", "start_time"]
        )
    )
    db.commit()


def replace_schedule(db: Session, facility: Facility, data: ScheduleData) -> int:
    """Înlocuiește programul facilității și curăță intervalele viitoare.

    Intervalele libere din viitor care nu mai sunt în program se șterg; cele
    care au istoric (rezervări anulate) se blochează, ca istoricul să rămână.
    Intervalele rezervate rămân, iar cele blocate pentru mentenanță nu se ating.
    Întoarce numărul rezervărilor viitoare rămase în afara noului program.
    """
    # Blocăm rândul facilității: două schimbări de program trimise în același
    # timp se aplică pe rând.
    db.execute(select(Facility.id).where(Facility.id == facility.id).with_for_update())
    db.execute(
        delete(FacilitySchedule).where(FacilitySchedule.facility_id == facility.id)
    )
    new_days = [
        FacilitySchedule(
            facility_id=facility.id,
            weekday=day.weekday,
            opens_at=day.opens_at,
            closes_at=day.closes_at,
        )
        for day in data.days
    ]
    db.add_all(new_days)
    facility.slot_minutes = data.slot_minutes
    schedule = {day.weekday: day for day in new_days}

    now = facility_service.romania_now(db)
    future = db.scalars(
        select(TimeSlot).where(
            TimeSlot.facility_id == facility.id,
            TimeSlot.status.in_(["free", "booked"]),
            (TimeSlot.slot_date > now.date())
            | ((TimeSlot.slot_date == now.date()) & (TimeSlot.start_time > now.time())),
        )
    ).all()
    outside = [
        slot for slot in future if not fits_schedule(slot, schedule, data.slot_minutes)
    ]
    free_ids = [slot.id for slot in outside if slot.status == "free"]
    bookings_outside = sum(1 for slot in outside if slot.status == "booked")

    if free_ids:
        has_history = exists().where(Booking.slot_id == TimeSlot.id)
        db.execute(
            update(TimeSlot)
            .where(TimeSlot.id.in_(free_ids), has_history)
            .values(status="blocked")
        )
        db.execute(delete(TimeSlot).where(TimeSlot.id.in_(free_ids), ~has_history))
    db.commit()
    return bookings_outside
