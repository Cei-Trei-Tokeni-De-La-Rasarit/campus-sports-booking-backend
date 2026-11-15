"""Datele primite și trimise de API pentru utilizatori.

Câmpurile din cod sunt în engleză, ca în baza de date, iar în JSON apar
numele din specificația OpenAPI, în română (prin alias).
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.models.user import User

UserRole = Literal["client", "manager", "administrator"]

# Valorile pentru rol din baza de date și echivalentul lor din API.
ROLE_FROM_DB: dict[str, str] = {
    "user": "client",
    "manager": "manager",
    "administrator": "administrator",
}

# Doar adresele instituționale USV pot crea cont.
ALLOWED_EMAIL_DOMAINS = ("student.usv.ro", "usv.ro")

# bcrypt folosește doar primii 72 de bytes din parolă și dă eroare peste această
# limită. O literă cu diacritice ocupă 2 bytes, deci verificăm bytes, nu litere.
MAX_PASSWORD_BYTES = 72


class UserRegister(BaseModel):
    """Datele trimise la crearea unui cont."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    # Spațiile de la capete se elimină doar din nume, nu și din parolă.
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
    ] = Field(alias="nume")
    email: EmailStr = Field(alias="email", max_length=150)
    password: str = Field(alias="parola", min_length=8, max_length=MAX_PASSWORD_BYTES)
    # strict=True: se acceptă doar true sau false, nu "da" sau 1.
    email_notifications: bool = Field(
        default=False, alias="notificari_email", strict=True
    )

    @field_validator("email")
    @classmethod
    def institutional_email(cls, email: str) -> str:
        """Acceptă doar emailurile instituționale și le scrie cu litere mici."""
        email = email.lower()
        if email.rsplit("@", 1)[1] not in ALLOWED_EMAIL_DOMAINS:
            raise ValueError(
                "Se acceptă doar adrese de email instituționale "
                "(@student.usv.ro sau @usv.ro)."
            )
        return email

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        """Respinge parolele mai lungi de 72 de bytes (limita bcrypt)."""
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Parola poate avea cel mult {MAX_PASSWORD_BYTES} de bytes."
            )
        return password


class UserRead(BaseModel):
    """Un utilizator, așa cum este trimis de API (fără parolă sau hash)."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int = Field(alias="id")
    name: str = Field(alias="nume")
    email: str = Field(alias="email")
    role: UserRole = Field(alias="rol")
    email_notifications: bool = Field(alias="notificari_email")

    @classmethod
    def from_model(cls, user: User) -> "UserRead":
        """Construiește răspunsul API pornind de la un rând din baza de date."""
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role=ROLE_FROM_DB[user.role],
            email_notifications=user.email_notifications,
        )


class UserLogin(BaseModel):
    """Datele trimise la autentificare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    email: EmailStr = Field(alias="email", max_length=150)
    password: Annotated[str, StringConstraints(min_length=1)] = Field(alias="parola")


class TokenResponse(BaseModel):
    """Răspunsul API după autentificare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    access_token: str = Field(alias="access_token", min_length=1)
    token_type: str = Field(default="bearer", alias="token_type")
    user: UserRead = Field(alias="user")


class UserLogin(BaseModel):
    """Datele trimise la autentificare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    email: EmailStr = Field(alias="email")
    password: str = Field(alias="parola")


class TokenResponse(BaseModel):
    """Răspunsul returnat la autentificare."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
