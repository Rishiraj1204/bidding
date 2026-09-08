from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    full_name: str = Field(..., min_length=2, max_length=255)
    organization_name: Optional[str] = Field(None, max_length=255)


class TokenUser(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    organization_name: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    is_active: bool
    is_superuser: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds
    user: TokenUser


class TokenPayload(BaseModel):
    sub: str  # User ID
    email: Optional[str] = None
    exp: Optional[int] = None
    roles: List[str] = []
    permissions: List[str] = []


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"
    status: str = "success"
