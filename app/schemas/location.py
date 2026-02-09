"""
Pydantic schemas for Location API
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class LocationHistoryResponse(BaseModel):
    id: UUID
    device_id: UUID
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    altitude: Optional[float] = None
    source: str
    ip_address: Optional[str] = None
    network_name: Optional[str] = None
    battery_level: Optional[float] = None
    recorded_at: datetime
    
    class Config:
        from_attributes = True


class LocationHistoryListResponse(BaseModel):
    locations: list[LocationHistoryResponse]
    device_id: UUID
    total: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LocationQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)


class AllDevicesLocationResponse(BaseModel):
    devices: list
    total: int
    online_count: int
    offline_count: int
