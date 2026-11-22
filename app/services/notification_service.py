"""Logica aplicației pentru notificări."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.models.notification import Notification
from app.models.time_slot import TimeSlot
from app.services import facility_service

WEEKDAYS = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]
MONTHS = [
    "ianuarie",
    "februarie",
    "martie",
    "aprilie",
    "mai",
    "iunie",
    "iulie",
    "august",
    "septembrie",
    "octombrie",
    "noiembrie",
    "decembrie",
]


class NotificationNotFoundError(Exception):
    """Notificarea nu există sau este a altui utilizator."""


def describe_slot(facility: Facility, slot: TimeSlot) -> str:
    """Textul unui interval, de exemplu:

    „Sala de tenis Nr. 3 · Luni, 23 noiembrie · 10:00 – 12:00”.
    """
    day = slot.slot_date
    date_text = f"{WEEKDAYS[day.weekday()]}, {day.day} {MONTHS[day.month - 1]}"
    hours = f"{slot.start_time:%H:%M} – {slot.end_time:%H:%M}"
    return f"{facility.name} · {date_text} · {hours}"


def add_notification(db: Session, user_id: int, type_: str, message: str) -> None:
    """Adaugă o notificare în sesiune, fără commit.

    Se salvează odată cu operația care a produs-o (rezervarea sau anularea),
    în aceeași tranzacție: dacă operația eșuează, nu rămâne nici notificarea.
    """
    db.add(
        Notification(
            user_id=user_id,
            type=type_,
            message=message,
            # În UTC, ca data creării rezervărilor.
            created_at=func.timezone("UTC", func.now()),
        )
    )


def list_notifications(
    db: Session, user_id: int, unread_only: bool = False
) -> list[Notification]:
    """Întoarce notificările utilizatorului, cele mai noi primele."""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return list(
        db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc())
        )
    )


def mark_notification(
    db: Session, user_id: int, notification_id: int, is_read: bool
) -> Notification:
    """Marchează notificarea utilizatorului ca citită sau necitită.

    Ridică NotificationNotFoundError dacă notificarea nu există sau e a
    altcuiva (același răspuns, ca nimeni să nu afle notificările altora).
    """
    if not 1 <= notification_id <= facility_service.MAX_DB_ID:
        raise NotificationNotFoundError()
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise NotificationNotFoundError()
    notification.is_read = is_read
    db.commit()
    db.refresh(notification)
    return notification
