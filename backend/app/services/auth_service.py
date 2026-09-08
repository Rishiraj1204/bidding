from typing import List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.rate_limit import limiter
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.auth import TokenResponse, TokenUser, UserLogin, UserRegister
from backend.app.schemas.user import UserCreate
from backend.app.services.user_service import create_user, get_user_by_email, init_rbac_system


def authenticate_user(db: Session, credentials: UserLogin) -> Tuple[User, str]:
    """
    Authenticate a user with email and password with brute-force protection.
    Returns the User model and signed JWT access token.
    Raises HTTPException for invalid credentials or inactive accounts.
    """
    # 1. Check Brute-Force lockout
    is_locked, seconds_remaining = limiter.is_locked_out(credentials.email)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to excessive failed attempts. Please retry in {seconds_remaining} seconds.",
            headers={"Retry-After": str(seconds_remaining)},
        )

    user = get_user_by_email(db, credentials.email)
    if not user:
        limiter.record_failed_login(credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.hashed_password):
        limiter.record_failed_login(credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact system administrator.",
        )

    # Reset failed attempts upon successful login
    limiter.reset_failed_logins(credentials.email)

    # Extract roles and permissions for token claims
    role_names: List[str] = [r.name for r in user.roles]
    perm_names: List[str] = list({p.name for r in user.roles for p in r.permissions})

    access_token = create_access_token(
        subject=user.id,
        email=user.email,
        roles=role_names,
        permissions=perm_names,
    )
    return user, access_token


def register_bidder(db: Session, reg_in: UserRegister) -> Tuple[User, str]:
    """
    Self-service registration for Bidders.
    Prevents privilege escalation by strictly assigning only BIDDER role.
    """
    # Create user with BIDDER role
    user_create = UserCreate(
        email=reg_in.email,
        password=reg_in.password,
        full_name=reg_in.full_name,
        organization_name=reg_in.organization_name,
        role_names=[UserRoleEnum.BIDDER.value],
        is_active=True,
        is_superuser=False,
    )
    user = create_user(db, user_create)

    # Generate token immediately
    role_names: List[str] = [r.name for r in user.roles]
    perm_names: List[str] = list({p.name for r in user.roles for p in r.permissions})

    token = create_access_token(
        subject=user.id,
        email=user.email,
        roles=role_names,
        permissions=perm_names,
    )
    return user, token


def format_token_response(user: User, token: str) -> TokenResponse:
    """Format user entity and token into API TokenResponse."""
    role_names = [r.name for r in user.roles]
    perm_names = list({p.name for r in user.roles for p in r.permissions})

    token_user = TokenUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_name=user.organization_name,
        roles=role_names,
        permissions=perm_names,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=token_user,
    )
