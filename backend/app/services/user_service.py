import uuid
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status

from backend.app.core.security import get_password_hash
from backend.app.models.user import User, Role, Permission, UserRoleEnum
from backend.app.schemas.user import UserCreate, UserUpdate

# Default system permissions mapped to roles per SRS / Architecture
DEFAULT_ROLE_PERMISSIONS: Dict[str, List[str]] = {
    UserRoleEnum.ADMIN.value: [
        "users.read",
        "users.write",
        "users.manage_roles",
        "tenders.read",
        "tenders.write",
        "tenders.publish",
        "tenders.delete",
        "bids.read_all",
        "documents.read_all",
        "compliance.read",
        "compliance.evaluate",
        "verification.read",
        "verification.execute",
        "reviews.read_all",
        "reviews.write",
        "reports.read",
        "reports.generate",
        "audit.read",
        "settings.write",
    ],
    UserRoleEnum.PROCUREMENT_OFFICER.value: [
        "tenders.read",
        "tenders.write",
        "tenders.publish",
        "bids.read_all",
        "documents.read_all",
        "compliance.read",
        "compliance.evaluate",
        "verification.read",
        "reviews.read_all",
        "reports.read",
        "reports.generate",
    ],
    UserRoleEnum.BIDDER.value: [
        "tenders.read",
        "bids.create",
        "bids.submit",
        "bids.read_own",
        "documents.upload",
        "documents.read_own",
    ],
    UserRoleEnum.REVIEWER.value: [
        "tenders.read",
        "bids.read_all",
        "documents.read_all",
        "compliance.read",
        "verification.read",
        "reviews.read_assigned",
        "reviews.write",
    ],
    UserRoleEnum.AUDITOR.value: [
        "tenders.read",
        "bids.read_all",
        "compliance.read",
        "verification.read",
        "reviews.read_all",
        "reports.read",
        "audit.read",
    ],
}


def init_rbac_system(db: Session) -> None:
    """Seed default permissions, roles, and role-permission mappings."""
    # 1. Collect all distinct permissions
    all_perm_names: Set[str] = set()
    for perm_list in DEFAULT_ROLE_PERMISSIONS.values():
        all_perm_names.update(perm_list)

    existing_perms = {p.name: p for p in db.query(Permission).all()}
    for perm_name in all_perm_names:
        if perm_name not in existing_perms:
            perm = Permission(
                id=str(uuid.uuid4()),
                name=perm_name,
                description=f"Permission for {perm_name}",
            )
            db.add(perm)
            existing_perms[perm_name] = perm
    db.commit()

    # 2. Seed roles and associate permissions
    existing_roles = {r.name: r for r in db.query(Role).options(selectinload(Role.permissions)).all()}
    for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        if role_name not in existing_roles:
            role = Role(
                id=str(uuid.uuid4()),
                name=role_name,
                description=f"System role: {role_name}",
            )
            db.add(role)
            db.commit()
            existing_roles[role_name] = role

        role = existing_roles[role_name]
        current_perm_names = {p.name for p in role.permissions}
        for p_name in perm_names:
            if p_name in existing_perms and p_name not in current_perm_names:
                role.permissions.append(existing_perms[p_name])
    db.commit()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Fetch user by unique email with eager loaded roles."""
    return (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.email == email.lower().strip())
        .first()
    )


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Fetch user by unique ID with eager loaded roles."""
    return (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .filter(User.id == user_id)
        .first()
    )


def get_users(db: Session, skip: int = 0, limit: int = 50) -> List[User]:
    """List users with pagination."""
    return (
        db.query(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_roles(db: Session) -> List[Role]:
    """List all system roles."""
    return db.query(Role).options(selectinload(Role.permissions)).all()


def get_permissions(db: Session) -> List[Permission]:
    """List all system permissions."""
    return db.query(Permission).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    """Create a new user with hashed password and assigned roles."""
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Initialize RBAC if not seeded yet
    role_count = db.query(Role).count()
    if role_count == 0:
        init_rbac_system(db)

    # Find requested roles
    roles: List[Role] = []
    if user_in.role_names:
        for r_name in user_in.role_names:
            role = db.query(Role).filter(Role.name == r_name.upper()).first()
            if role:
                roles.append(role)
    if not roles:
        default_role = db.query(Role).filter(Role.name == UserRoleEnum.BIDDER.value).first()
        if default_role:
            roles.append(default_role)

    user = User(
        id=str(uuid.uuid4()),
        email=user_in.email.lower().strip(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        organization_name=user_in.organization_name.strip() if user_in.organization_name else None,
        is_active=user_in.is_active,
        is_superuser=user_in.is_superuser,
    )
    user.roles.extend(roles)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: str, user_in: UserUpdate) -> User:
    """Update user attributes, status, or role assignments."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user_in.email is not None:
        new_email = user_in.email.lower().strip()
        if new_email != user.email:
            existing = get_user_by_email(db, new_email)
            if existing and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use by another user",
                )
            user.email = new_email

    if user_in.full_name is not None:
        user.full_name = user_in.full_name.strip()

    if user_in.organization_name is not None:
        user.organization_name = user_in.organization_name.strip()

    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    if user_in.is_superuser is not None:
        user.is_superuser = user_in.is_superuser

    if user_in.role_names is not None:
        new_roles = []
        for r_name in user_in.role_names:
            role = db.query(Role).filter(Role.name == r_name.upper()).first()
            if role:
                new_roles.append(role)
        user.roles = new_roles

    db.commit()
    db.refresh(user)
    return user
