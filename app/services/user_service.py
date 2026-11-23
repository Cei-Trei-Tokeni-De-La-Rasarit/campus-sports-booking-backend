"""Logica aplicației pentru rolurile utilizatorilor și alocarea facilităților.

Administratorul schimbă rolul unui utilizator și, pentru manageri, alege
facilitățile pe care aceștia le pot edita (KAN-94).
"""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.facility import Facility
from app.models.facility_manager import FacilityManager
from app.models.user import User
from app.schemas.user import ROLE_TO_DB, RoleUpdate
from app.services import facility_service


class UserNotFoundError(Exception):
    """Utilizatorul cerut nu există."""


class OwnRoleChangeError(Exception):
    """Administratorul încearcă să își schimbe propriul rol."""


class UnknownFacilitiesError(Exception):
    """Unele facilități din lista de alocare nu există."""

    def __init__(self, facility_ids: list[int]) -> None:
        super().__init__(facility_ids)
        self.facility_ids = facility_ids


def get_assigned_facility_ids(db: Session, manager_id: int) -> list[int]:
    """ID-urile facilităților alocate unui manager, în ordine crescătoare."""
    return list(
        db.scalars(
            select(FacilityManager.facility_id)
            .where(FacilityManager.manager_id == manager_id)
            .order_by(FacilityManager.facility_id)
        )
    )


def manages_facility(db: Session, manager_id: int, facility_id: int) -> bool:
    """Spune dacă facilitatea este alocată managerului."""
    return (
        db.get(FacilityManager, {"manager_id": manager_id, "facility_id": facility_id})
        is not None
    )


def find_missing_facilities(db: Session, facility_ids: list[int]) -> list[int]:
    """Întoarce, în ordine, ID-urile din listă care nu există în baza de date."""
    if not facility_ids:
        return []
    existing = set(db.scalars(select(Facility.id).where(Facility.id.in_(facility_ids))))
    return sorted(set(facility_ids) - existing)


def change_role(db: Session, admin: User, user_id: int, data: RoleUpdate) -> User:
    """Schimbă rolul unui utilizator și înlocuiește facilitățile lui alocate.

    Un manager primește exact facilitățile din `data`; un utilizator care nu
    (mai) este manager rămâne fără alocări.
    """
    if not 1 <= user_id <= facility_service.MAX_DB_ID:
        raise UserNotFoundError
    # Blocăm rândul utilizatorului: două schimbări de rol trimise în același
    # timp pentru același om se aplică pe rând, iar alocările nu se amestecă.
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserNotFoundError
    # Fără această regulă, aplicația ar putea rămâne fără administrator.
    if user.id == admin.id:
        raise OwnRoleChangeError

    facility_ids = data.assigned_facility_ids or []
    missing = find_missing_facilities(db, facility_ids)
    if missing:
        raise UnknownFacilitiesError(missing)

    user.role = ROLE_TO_DB[data.role]
    db.execute(delete(FacilityManager).where(FacilityManager.manager_id == user.id))
    db.add_all(
        FacilityManager(manager_id=user.id, facility_id=facility_id)
        for facility_id in facility_ids
    )
    try:
        db.commit()
    except IntegrityError as error:
        # O facilitate a fost ștearsă între verificare și salvare.
        db.rollback()
        raise UnknownFacilitiesError(
            find_missing_facilities(db, facility_ids)
        ) from error
    db.refresh(user)
    return user
