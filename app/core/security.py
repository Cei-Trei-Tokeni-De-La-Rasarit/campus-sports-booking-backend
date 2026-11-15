"""Utilitare pentru criptarea parolelor și generarea/validarea token-urilor JWT."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SECRET_KEY = os.getenv("SECRET_KEY", "schimba-aceasta-cheie-secreta-in-productie")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 ore


def hash_password(password: str) -> str:
    """Generează hash-ul bcrypt pentru o parolă în clar."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifică dacă parola în clar corespunde hash-ului salvat în baza de date."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_access_token(user_id: int, role: str) -> str:
    """Generează un token JWT semnat cu ID-ul și rolul utilizatorului."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodează și validează un token JWT."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
