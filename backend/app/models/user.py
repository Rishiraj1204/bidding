import enum
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Table, Column, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    PROCUREMENT_OFFICER = "PROCUREMENT_OFFICER"
    BIDDER = "BIDDER"
    REVIEWER = "REVIEWER"
    AUDITOR = "AUDITOR"


# Association table for Role <-> Permission (Many-to-Many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for User <-> Role (Many-to-Many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()),
)


class Permission(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    roles: Mapped[List["Role"]] = relationship("Role", secondary=role_permissions, back_populates="permissions")


class Role(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    permissions: Mapped[List["Permission"]] = relationship("Permission", secondary=role_permissions, back_populates="roles")
    users: Mapped[List["User"]] = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")
    
    # Relationships for domain ownership
    created_tenders: Mapped[List["Tender"]] = relationship("Tender", back_populates="created_by", cascade="all, delete-orphan")
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="bidder", cascade="all, delete-orphan")
    assigned_reviews: Mapped[List["ReviewTask"]] = relationship("ReviewTask", back_populates="assigned_to")
    review_decisions: Mapped[List["ReviewDecision"]] = relationship("ReviewDecision", back_populates="reviewer")
    reports_generated: Mapped[List["Report"]] = relationship("Report", back_populates="generated_by")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="actor")
