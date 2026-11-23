"""Punctul de pornire al aplicației Campus Sports Booking."""

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import engine
from app.routers import (
    auth,
    booking_router,
    facility_router,
    notification_router,
    user_router,
)

# Importat la pornire, ca o configurație de email greșită (EMAIL_MODE=smtp fără
# datele contului) să oprească serverul imediat, nu abia la primul email.
from app.services import email_service  # noqa: F401
from app.validation_messages import describe_errors

# Mesajele de tip INFO din aplicație (de exemplu, emailurile din modul
# consolă) apar în terminalul serverului, lângă cele ale lui uvicorn.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger(__name__)

# Adresele de la care frontend-ul are voie să trimită cereri (CORS),
# separate prin virgulă. Implicit, serverul de dezvoltare Vite.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app = FastAPI(title="Campus Sports Booking API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    # Authorization: frontend-ul trimite token-ul JWT (Bearer) în acest header.
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(facility_router.router)
app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(user_router.router)
app.include_router(booking_router.router)
app.include_router(notification_router.router)


@app.exception_handler(StarletteHTTPException)
def handle_http_error(_request: Request, error: StarletteHTTPException) -> JSONResponse:
    """Trimite erorile în formatul din specificație: {"mesaj": "..."}."""
    return JSONResponse(status_code=error.status_code, content={"mesaj": error.detail})


@app.exception_handler(RequestValidationError)
def handle_validation_error(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    """Datele greșite primesc 400, ca în specificația API, cu mesajul în română."""
    return JSONResponse(
        status_code=400, content={"mesaj": describe_errors(list(error.errors()))}
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
