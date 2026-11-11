"""Punctul de pornire al aplicației Campus Sports Booking."""

import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

logger = logging.getLogger(__name__)

app = FastAPI(title="Campus Sports Booking API", version="0.1.0")


@app.get("/")
def health_check() -> dict[str, str]:
    """Verifică dacă serverul rulează și se poate conecta la baza de date."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        logger.error("Conectarea la baza de date a eșuat: %s", error)
        raise HTTPException(
            status_code=503, detail="Baza de date nu este disponibilă."
        ) from error
    return {"status": "ok"}
