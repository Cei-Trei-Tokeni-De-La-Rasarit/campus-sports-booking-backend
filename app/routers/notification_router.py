"""Endpoint-urile API pentru notificări (/notificari)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services import notification_service

router = APIRouter(prefix="/notificari", tags=["Notificări și Feedback"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    unread_only: Annotated[bool, Query(alias="necitite")] = False,
) -> list[NotificationRead]:
    """Notificările utilizatorului autentificat, cele mai noi primele."""
    notifications = notification_service.list_notifications(
        db, current_user.id, unread_only
    )
    return [NotificationRead.from_model(n) for n in notifications]


@router.patch("/{notification_id}", response_model=NotificationRead)
def mark_notification(
    notification_id: int,
    data: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationRead:
    """Marchează o notificare proprie ca citită (sau din nou necitită)."""
    try:
        notification = notification_service.mark_notification(
            db, current_user.id, notification_id, data.is_read
        )
    except notification_service.NotificationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificarea nu există."
        ) from error
    return NotificationRead.from_model(notification)
