"""Logica aplicației pentru regulamentele facilităților."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.regulation import Regulation


def get_regulation(db: Session, facility_id: int) -> Regulation | None:
    """Întoarce regulamentul unei facilități sau None dacă nu există."""
    return db.scalar(select(Regulation).where(Regulation.facility_id == facility_id))


def save_regulation(db: Session, facility_id: int, content: str) -> Regulation:
    """Înlocuiește regulamentul facilității sau îl creează, dacă nu are unul.

    ON CONFLICT pe facility_id (UNIQUE): două cereri trimise în același timp
    pentru o sală fără regulament nu dau eroare, ci rămâne ultimul text.
    """
    statement = insert(Regulation).values(facility_id=facility_id, content=content)
    regulation = db.scalars(
        statement.on_conflict_do_update(
            index_elements=[Regulation.facility_id],
            set_={"content": statement.excluded.content},
        ).returning(Regulation),
        # Dacă regulamentul era deja încărcat în sesiune, primește textul nou.
        execution_options={"populate_existing": True},
    ).one()
    db.commit()
    return regulation
