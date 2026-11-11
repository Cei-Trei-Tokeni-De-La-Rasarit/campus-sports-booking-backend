"""Conexiunea la baza de date PostgreSQL."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Citește variabilele din fișierul .env, ca datele de conectare să nu fie în cod.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise RuntimeError("Lipsește variabila DATABASE_URL (vezi .env.example).")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Clasa de bază pentru modelele SQLAlchemy."""


def get_db() -> Generator[Session, None, None]:
    """Deschide o sesiune pentru o cerere și o închide la final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
