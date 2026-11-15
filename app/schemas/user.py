"""Datele primite și trimise de API pentru utilizatori."""

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

ROLE_FROM_DB: dict[str, str] = {
    "user": "client",
    "manager": "manager",
    "administrator": "administrator",
}

ALLOWED_EMAIL_DOMAINS = ("student.usv.ro", "usv.ro")
MAX_PASSWORD_BYTES = 72


class UserRegister(BaseModel):
    """Datele trimise la crearea unui cont."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
    ] = Field(alias="nume")
    email: EmailStr = Field(alias="email", max_length=150)
    password: str = Field(alias="parola", min_length=8, max_length=MAX_PASSWORD_BYTES)
    email_notifications: bool = Field(
        default=False, alias="notificari_email", strict=True
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Normalizează spațiile și literele înainte de validarea adresei."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("email")
    @classmethod
    def institutional_email(cls, email: EmailStr) -> EmailStr:
        """Acceptă doar emailurile instituționale și le scrie cu litere mici."""
        domain = str(email).rsplit("@", 1)[-1]
        if domain not in ALLOWED_EMAIL_DOMAINS:
            raise ValueError(
                "Se acceptă doar adrese de email instituționale "
                "(@student.usv.ro sau @usv.ro)."
            )
        return email

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        """Respinge parolele mai lungi de limita bcrypt în bytes."""
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Parola poate avea cel mult {MAX_PASSWORD_BYTES} de bytes."
            )
        return password


class UserRead(BaseModel):
    """Un utilizator trimis de API, fără parolă sau hash."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: int = Field(alias="id")
    name: str = Field(alias="nume")
    email: str = Field(alias="email")
    role: UserRole = Field(alias="rol")
    email_notifications: bool = Field(alias="notificari_email")

    @classmethod
    def from_model(cls, user: User) -> "UserRead":
        """Construiește răspunsul API dintr-un rând din baza de date."""
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

    email: EmailStr = Field(alias="email")
    password: str = Field(alias="parola")


class TokenResponse(BaseModel):
    """Răspunsul returnat la autentificare."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
