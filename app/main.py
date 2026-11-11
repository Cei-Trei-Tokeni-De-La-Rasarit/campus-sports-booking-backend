"""Punctul de pornire al aplicației Campus Sports Booking."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import engine
from app.routers import facility_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Campus Sports Booking API", version="0.1.0")
app.include_router(facility_router.router)


@app.exception_handler(StarletteHTTPException)
def handle_http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
    """Trimite erorile în formatul din specificație: {"mesaj": "..."}."""
    return JSONResponse(status_code=error.status_code, content={"mesaj": error.detail})


@app.exception_handler(RequestValidationError)
def handle_validation_error(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    """Datele greșite primesc 400, ca în specificația API."""
    problems = [
        f"{'.'.join(str(part) for part in item['loc'][1:])}: {item['msg']}"
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=400, content={"mesaj": "Date invalide. " + "; ".join(problems)}
    )


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
