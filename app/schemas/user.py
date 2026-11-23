"""Datele primite și trimise de API pentru utilizatori."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.user import User
from app.schemas.booking import MAX_DB_ID

UserRole = Literal["client", "manager", "administrator"]

ROLE_FROM_DB: dict[str, str] = {
    "user": "client",
    "manager": "manager",
    "administrator": "administrator",
}
ROLE_TO_DB: dict[str, str] = {api: db for db, api in ROLE_FROM_DB.items()}

# strict=True: id-urile se dau ca numere întregi, nu "1", 1.0 sau true.
FacilityId = Annotated[int, Field(strict=True, ge=1, le=MAX_DB_ID)]

ALLOWED_EMAIL_DOMAINS = ("student.usv.ro", "usv.ro")
MAX_PASSWORD_BYTES = 72


def _validate_password_bytes(password: str) -> str:
    """Respinge parolele mai lungi de limita bcrypt în bytes."""
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Parola poate avea cel mult {MAX_PASSWORD_BYTES} de bytes.")
    return password


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
        return _validate_password_bytes(password)


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


class UserAdminRead(UserRead):
    """Un utilizator din lista administratorului, cu sălile alocate managerilor."""

    # Pentru alt rol decât manager, lista e goală.
    assigned_facility_ids: list[int] = Field(alias="facilitati_alocate")


class UserFilters(BaseModel):
    """Filtrele pentru `GET /utilizatori`, primite în adresă (query)."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, str_strip_whitespace=True
    )

    role: UserRole | None = Field(default=None, alias="rol")
    # Caută în nume și în email; un text gol înseamnă „fără filtru”.
    search: str | None = Field(default=None, alias="cautare", max_length=100)

    @field_validator("search")
    @classmethod
    def empty_search_to_none(cls, value: str | None) -> str | None:
        """Un text gol sau doar din spații nu filtrează nimic."""
        return value or None


class RoleUpdate(BaseModel):
    """Datele primite la `PUT /utilizatori/{id}/rol` (doar administrator)."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    role: UserRole = Field(alias="rol")
    # Doar pentru rolul manager. Lipsă înseamnă că managerul nu are facilități.
    assigned_facility_ids: list[FacilityId] | None = Field(
        default=None, alias="facilitati_alocate"
    )

    @model_validator(mode="after")
    def check_assigned_facilities(self) -> "RoleUpdate":
        """Facilitățile se alocă doar managerilor și fiecare apare o singură dată."""
        ids = self.assigned_facility_ids
        if ids is None:
            return self
        if self.role != "manager":
            raise ValueError("Facilitățile se pot aloca doar pentru rolul manager.")
        if len(ids) != len(set(ids)):
            raise ValueError("Fiecare facilitate poate apărea o singură dată.")
        return self


class PasswordResetRequest(BaseModel):
    """Datele primite la `POST /auth/resetare-parola`."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    email: EmailStr = Field(alias="email", max_length=150)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Aceeași adresă, oricum ar fi scrisă (spații, majuscule)."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


# Token-ul din link are 43 de caractere; lăsăm loc, dar nu texte uriașe.
MAX_RESET_TOKEN_LENGTH = 100


class PasswordResetConfirm(BaseModel):
    """Datele primite la `POST /auth/resetare-parola/confirmare`."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    token: str = Field(
        alias="token", min_length=1, max_length=MAX_RESET_TOKEN_LENGTH, strict=True
    )
    # Aceleași reguli ca la înregistrare.
    new_password: str = Field(
        alias="parola_noua", min_length=8, max_length=MAX_PASSWORD_BYTES
    )

    @field_validator("new_password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        return _validate_password_bytes(password)


class MessageRead(BaseModel):
    """Un răspuns care conține doar un mesaj pentru utilizator."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    message: str = Field(alias="mesaj")


class UserLogin(BaseModel):
    """Datele trimise la autentificare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    email: EmailStr = Field(alias="email")
    password: str = Field(alias="parola", min_length=8, max_length=MAX_PASSWORD_BYTES)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, password: str) -> str:
        return _validate_password_bytes(password)


class TokenResponse(BaseModel):
    """Răspunsul returnat la autentificare."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    token: str = Field(alias="token")
    user: UserRead = Field(alias="utilizator")
