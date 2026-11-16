"""Dependențe FastAPI pentru controlul accesului pe bază de rol (RBAC)."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.models.user import User
from app.routers.auth import get_current_user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Permite accesul doar utilizatorilor care au unul dintre rolurile specificate."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nu ai permisiunile necesare pentru această acțiune.",
            )
        return current_user

    return role_checker


require_admin = require_roles("administrator")
require_manager_or_admin = require_roles("administrator", "manager")
