"""Schemele Pydantic pentru utilizatori."""

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.models.user import User

UserRole = Literal["user", "administrator", "manager"]

StrippedName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
]


class UserRegister(BaseModel):
    """Datele trimise la înregistrare (Sign Up)."""

    name: StrippedName
    email: EmailStr = Field(..., max_length=150)
    password: str = Field(..., min_length=8, max_length=128)
    email_notifications: bool = False


class UserRead(BaseModel):
    """Reprezentarea publică a unui utilizator (fără password_hash)."""

    id: int
    name: str
    email: str
    role: UserRole
    email_notifications: bool

    @classmethod
    def from_model(cls, user: User) -> "UserRead":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,  # type: ignore[arg-type]
            email_notifications=user.email_notifications,
        )
class UserLogin(BaseModel):
    """Datele trimise la autentificare (Sign In)."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Răspunsul returnat la Sign In."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead