from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.auth import (
    LogoutResponse,
    TokenResponse,
    TokenUser,
    UserLogin,
    UserRegister,
)
from backend.app.services.auth_service import (
    authenticate_user,
    format_token_response,
    register_bidder,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Bidder",
)
def register(
    reg_data: UserRegister,
    db: Session = Depends(get_db),
):
    """
    Public registration endpoint for bidders.
    Creates account with BIDDER role and returns authentication token.
    """
    user, token = register_bidder(db, reg_data)
    return format_token_response(user, token)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User and Issue Token",
)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Authenticate user with email and password.
    Returns JWT bearer token and user role information.
    """
    user, token = authenticate_user(db, credentials)
    return format_token_response(user, token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="User Logout",
)
def logout(
    current_user: User = Depends(get_current_active_user),
):
    """
    Logout endpoint. Client should discard JWT token.
    """
    return LogoutResponse(
        message=f"Successfully logged out user {current_user.email}",
        status="success",
    )


@router.get(
    "/me",
    response_model=TokenUser,
    summary="Get Current Authenticated User",
)
def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """
    Fetch the currently logged in user profile, assigned roles, and permissions.
    """
    role_names = [r.name for r in current_user.roles]
    perm_names = list({p.name for r in current_user.roles for p in r.permissions})

    return TokenUser(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        organization_name=current_user.organization_name,
        roles=role_names,
        permissions=perm_names,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
    )
