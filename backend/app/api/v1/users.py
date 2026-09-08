from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import (
    check_resource_ownership,
    get_current_active_user,
    require_roles,
)
from backend.app.models.user import User, UserRoleEnum
from backend.app.schemas.user import (
    PermissionResponse,
    RoleResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from backend.app.services.user_service import (
    create_user,
    get_permissions,
    get_roles,
    get_user_by_id,
    get_users,
    update_user,
)

router = APIRouter()


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List System Users",
)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.ADMIN.value, UserRoleEnum.PROCUREMENT_OFFICER.value)),
):
    """List system users (Requires ADMIN or PROCUREMENT_OFFICER role)."""
    return get_users(db, skip=skip, limit=limit)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create User with Role Assignment",
)
def create_new_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRoleEnum.ADMIN.value)),
):
    """Admin-only endpoint to provision users and assign roles."""
    return create_user(db, user_in)


@router.get(
    "/roles/list",
    response_model=List[RoleResponse],
    summary="List Available Roles",
)
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all available system roles and their assigned permissions."""
    return get_roles(db)


@router.get(
    "/permissions/list",
    response_model=List[PermissionResponse],
    summary="List Available Permissions",
)
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all system permissions."""
    return get_permissions(db)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User By ID",
)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Fetch user details by ID (Requires ADMIN role or self-ownership)."""
    check_resource_ownership(current_user, owner_id=user_id, allowed_override_roles=[UserRoleEnum.ADMIN.value])
    user = get_user_by_id(db, user_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update User Profile",
)
def update_user_profile(
    user_id: str,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update user profile or status (Requires ADMIN role or self-ownership)."""
    check_resource_ownership(current_user, owner_id=user_id, allowed_override_roles=[UserRoleEnum.ADMIN.value])
    
    # Non-admin users cannot change role assignments, active status, or superuser flag
    user_role_names = {r.name for r in current_user.roles}
    if not current_user.is_superuser and "ADMIN" not in user_role_names:
        user_in.role_names = None
        user_in.is_active = None
        user_in.is_superuser = None

    return update_user(db, user_id=user_id, user_in=user_in)
