"""Pornește backend-ul pentru testele end-to-end din frontend (KAN-104).

1. Golește baza de test (`TEST_DATABASE_URL` din `.env`) și o reîncarcă din
   `app/database/shemas.sql` și `app/database/seed.sql`, ca fiecare rulare să
   pornească de la aceleași date.
2. Pornește serverul pe portul 8001 (separat de cel de dezvoltare, 8000) și
   acceptă cereri doar de la frontend-ul pornit de teste (portul 5174).

Rulare, din folderul backend-ului (o face singur `npm run test:e2e`):

    python scripts/e2e_server.py
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BACKEND_DIR / "app" / "database"
PORT = 8001
FRONTEND_ORIGIN = "http://localhost:5174"

logger = logging.getLogger("e2e_server")


def test_database_url() -> str:
    """Adresa bazei de test; refuză orice bază al cărei nume nu conține „test”."""
    load_dotenv(BACKEND_DIR / ".env")
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        sys.exit("Lipsește TEST_DATABASE_URL în .env (vezi .env.example).")
    # Scriptul golește baza, deci nu are voie să atingă baza echipei.
    if "test" not in (make_url(url).database or ""):
        sys.exit("TEST_DATABASE_URL trebuie să indice o bază de test.")
    return url


def reset_database(url: str) -> None:
    """Golește baza de test și o încarcă din scripturile proiectului."""
    with create_engine(url).begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for script in ("shemas.sql", "seed.sql"):
            sql = (DATABASE_DIR / script).read_text(encoding="utf-8")
            connection.exec_driver_sql(sql)
    logger.info("Baza de test a fost reîncărcată din shemas.sql și seed.sql.")


def main() -> None:
    """Reîncarcă baza de test și pornește serverul pentru testele end-to-end."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    url = test_database_url()
    reset_database(url)

    # Aplicația citește aceste variabile la import, deci le setăm înainte.
    os.environ["DATABASE_URL"] = url
    os.environ["CORS_ORIGINS"] = FRONTEND_ORIGIN
    sys.path.insert(0, str(BACKEND_DIR))
    import uvicorn

    uvicorn.run("app.main:app", port=PORT)


if __name__ == "__main__":
    main()
