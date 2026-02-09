"""
Pydantic schemas for Alert API
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.alert import AlertType, AlertSeverity


class AlertBase(BaseModel):
    alert_type: AlertType
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = Field(..., min_length=1, max_length=255)
    message: Optional[str] = None


class AlertCreate(AlertBase):
    device_id: UUID
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_id: Optional[UUID] = None


class AlertAcknowledge(BaseModel):
    notes: Optional[str] = None


class AlertResolve(BaseModel):
    notes: Optional[str] = None


class AlertResponse(AlertBase):
    id: UUID
    device_id: UUID
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geofence_id: Optional[UUID] = None
    is_acknowledged: bool
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertWithDeviceInfo(AlertResponse):
    device_asset_id: Optional[str] = None
    device_name: Optional[str] = None
    employee_name: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: list[AlertWithDeviceInfo]
    total: int
    unacknowledged_count: int
    page: int
    per_page: int


class AlertStats(BaseModel):
    total: int
    unacknowledged: int
    by_severity: dict
    by_type: dict
