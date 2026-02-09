"""
Pydantic schemas for Device API
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.models.device import DeviceStatus, DeviceType


# Base schemas
class DeviceBase(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=100)
    asset_id: str = Field(..., min_length=1, max_length=50)
    device_name: Optional[str] = None
    device_type: DeviceType = DeviceType.LAPTOP
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    # Mobile device fields
    imei: Optional[str] = Field(None, max_length=20)
    imei2: Optional[str] = Field(None, max_length=20)
    phone_number: Optional[str] = Field(None, max_length=20)
    carrier: Optional[str] = Field(None, max_length=50)


# Create schemas
class DeviceCreate(DeviceBase):
    assigned_user_id: Optional[UUID] = None


class DeviceRegister(BaseModel):
    """Schema for agent registration"""
    serial_number: str
    asset_id: str
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    mac_address: Optional[str] = None
    agent_version: str


class DeviceAgentPing(BaseModel):
    """Schema for agent status ping"""
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)
    altitude: Optional[float] = None
    location_source: str = "IP"  # GPS, WiFi, IP, HYBRID
    ip_address: Optional[str] = None
    network_name: Optional[str] = None
    battery_level: Optional[float] = Field(None, ge=0, le=100)
    is_charging: Optional[bool] = None
    agent_version: str
    
    @field_validator('location_source')
    @classmethod
    def validate_source(cls, v):
        valid_sources = ['GPS', 'WiFi', 'IP', 'HYBRID']
        if v not in valid_sources:
            raise ValueError(f'location_source must be one of {valid_sources}')
        return v


# Update schemas
class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[DeviceType] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    employee_name: Optional[str] = None
    department: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    # Admin can manually update location if needed
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None


class DeviceLockRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class DeviceWipeRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    confirm: bool = False


# Response schemas
class DeviceResponse(DeviceBase):
    id: UUID
    status: DeviceStatus
    is_registered: bool
    agent_installed: bool
    agent_version: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_location_accuracy: Optional[float] = None
    last_location_source: Optional[str] = None
    last_ip_address: Optional[str] = None
    last_seen: Optional[datetime] = None
    is_encrypted: bool
    is_locked: bool
    is_wiped: bool
    consent_given: bool
    assigned_user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    devices: list[DeviceResponse]
    total: int
    online_count: int
    offline_count: int
    page: int
    per_page: int


class DeviceRegistrationResponse(BaseModel):
    device_id: UUID
    agent_token: str
    message: str


class DeviceLocationResponse(BaseModel):
    device_id: UUID
    asset_id: str
    device_name: Optional[str]
    employee_name: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    accuracy: Optional[float]
    location_source: Optional[str]
    last_seen: Optional[datetime]
    status: DeviceStatus


class CommandInfo(BaseModel):
    id: Optional[str] = None
    type: str  # lock, unlock, restart, shutdown, screenshot, message, execute
    payload: Optional[dict] = None  # For message content, execute command, etc.


class DeviceCommandResponse(BaseModel):
    command: Optional[str] = None  # Deprecated: single command (lock, wipe, update, none)
    command_id: Optional[str] = None
    message: Optional[str] = None
    commands: Optional[list[CommandInfo]] = None  # New: list of pending commands
