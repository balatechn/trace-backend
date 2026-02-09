"""
Pydantic schemas for Audit Log API
"""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel
from app.models.audit import AuditAction


class AuditLogCreate(BaseModel):
    action: AuditAction
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_identifier: Optional[str] = None
    description: Optional[str] = None
    details: Optional[dict] = None


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: AuditAction
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
    target_identifier: Optional[str] = None
    description: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    per_page: int


class AuditLogQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    action: Optional[AuditAction] = None
    user_id: Optional[UUID] = None
    target_type: Optional[str] = None
    target_id: Optional[UUID] = None
