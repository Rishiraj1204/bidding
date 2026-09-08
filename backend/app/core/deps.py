from typing import Callable, Generator, List, Optional, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session, selectinload

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import decode_access_token
from backend.app.models.user import User, Role, Permission

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """Validate JWT token and return the authenticated user with loaded roles & permissions."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise credentials_exception

    # Query user with eager-loaded roles and permissions
    user = (
        db.query(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def get_user_roles(user: User) -> Set[str]:
    """Extract role names for a user."""
    return {role.name for role in user.roles}


def get_user_permissions(user: User) -> Set[str]:
    """Extract all distinct permission names across all user roles."""
    perms: Set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            perms.add(perm.name)
    return perms


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory ensuring user has at least one of the specified roles or is superuser."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.is_superuser:
            return current_user

        user_roles = get_user_roles(current_user)
        if "ADMIN" in user_roles:
            return current_user

        if any(role in user_roles for role in allowed_roles):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Requires one of roles: {', '.join(allowed_roles)}",
        )
    return role_checker


def require_permissions(*required_perms: str) -> Callable:
    """Dependency factory ensuring user possesses all required permissions or is superuser."""
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.is_superuser:
            return current_user

        user_roles = get_user_roles(current_user)
        if "ADMIN" in user_roles:
            return current_user

        user_perms = get_user_permissions(current_user)
        missing_perms = [p for p in required_perms if p not in user_perms]

        if not missing_perms:
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Missing required permissions: {', '.join(missing_perms)}",
        )
    return permission_checker


def check_resource_ownership(
    user: User,
    owner_id: str,
    allowed_override_roles: Optional[List[str]] = None,
) -> bool:
    """
    Validate whether a user owns a resource or has an override role (e.g. ADMIN, PROCUREMENT_OFFICER).
    Raises HTTP 403 if forbidden.
    """
    if user.is_superuser:
        return True

    user_roles = get_user_roles(user)
    if "ADMIN" in user_roles:
        return True

    if allowed_override_roles:
        if any(role in user_roles for role in allowed_override_roles):
            return True

    if user.id == owner_id:
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Resource access denied: you do not have permission to access or modify this resource.",
    )
