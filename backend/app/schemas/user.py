from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class PermissionBase(BaseModel):
    name: str
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleResponse(RoleBase):
    id: str
    permissions: List[PermissionResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    organization_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role_names: Optional[List[str]] = Field(default_factory=lambda: ["BIDDER"])


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    organization_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_names: Optional[List[str]] = None


class UserResponse(UserBase):
    id: str
    roles: List[RoleResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
