"""Utilitare pentru criptarea parolelor."""

import bcrypt


def hash_password(password: str) -> str:
    """Generează hash-ul bcrypt pentru o parolă în clar."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
