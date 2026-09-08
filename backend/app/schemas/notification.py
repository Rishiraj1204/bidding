from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    notification_type: str
    is_read: bool
    related_resource_type: Optional[str] = None
    related_resource_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int
