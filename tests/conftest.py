"""Pregătirea testelor: baza de date de test și clientul HTTP."""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if TEST_DATABASE_URL is None:
    raise RuntimeError("Lipsește variabila TEST_DATABASE_URL (vezi .env.example).")

# Testele golesc baza de date, așa că refuzăm orice bază care nu e de test.
if "test" not in (make_url(TEST_DATABASE_URL).database or ""):
    raise RuntimeError("TEST_DATABASE_URL trebuie să indice o bază de test.")

# Aplicația trebuie să folosească baza de test, deci setăm adresa
# înainte de a importa codul aplicației.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SCHEMA_FILE = Path(__file__).parent.parent / "app" / "database" / "shemas.sql"

engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def create_schema() -> None:
    """Creează tabelele o dată, din scriptul bazei de date, la începutul testelor."""
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        connection.exec_driver_sql(SCHEMA_FILE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def empty_tables() -> None:
    """Golește toate tabelele înainte de fiecare test."""
    with engine.begin() as connection:
        tables = connection.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).all()
        names = ", ".join(f'"{table}"' for table in tables)
        connection.exec_driver_sql(f"TRUNCATE {names} RESTART IDENTITY CASCADE")


@pytest.fixture
def add_time_slot() -> Callable[[int], None]:
    """Adaugă un interval în calendar pentru facilitatea cu id-ul dat.

    Încă nu există endpoint pentru calendar, așa că intervalul se scrie direct
    în baza de test.
    """

    def add(facility_id: int) -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO time_slot (facility_id, slot_date, start_time, "
                    "end_time) VALUES (:id, '2026-12-01', '10:00', '11:00')"
                ),
                {"id": facility_id},
            )

    return add


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Clientul HTTP care trimite cereri către aplicație."""
    with TestClient(app) as test_client:
        yield test_client
