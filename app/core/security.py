"""Utilitare pentru criptarea parolelor și generarea/validarea token-urilor JWT."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

# Cheia HS256 trebuie să fie cel puțin cât rezultatul SHA-256 (32 de bytes);
# o cheie scurtă poate fi ghicită și atunci oricine își poate face token-uri.
MIN_SECRET_KEY_LENGTH = 32


def check_secret_key(secret_key: str | None) -> str:
    """Întoarce cheia dacă e destul de lungă; altfel oprește serverul."""
    if not secret_key:
        raise RuntimeError("Lipsește variabila SECRET_KEY (vezi .env.example).")
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY trebuie să aibă cel puțin {MIN_SECRET_KEY_LENGTH} de "
            "caractere. Generează una nouă (vezi README, pasul 3)."
        )
    return secret_key


SECRET_KEY = check_secret_key(os.getenv("SECRET_KEY"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 ore


def hash_password(password: str) -> str:
    """Generează hash-ul bcrypt pentru o parolă în clar."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# Un hash bcrypt valid pentru o parolă pe care nu o are nimeni. Îl verificăm
# când emailul nu există, ca răspunsul să dureze la fel de mult ca pentru o
# parolă greșită: altfel, din timpul de răspuns s-ar afla ce emailuri au cont.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"parola-care-nu-exista", bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifică dacă parola în clar corespunde hash-ului salvat în baza de date.

    Un hash invalid în bază (de exemplu, pus de mână) înseamnă „parolă
    greșită”, nu eroare 500.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


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
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
