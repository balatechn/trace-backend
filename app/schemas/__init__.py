"""
Pydantic schemas package
"""
from app.schemas.user import (
    UserBase, UserCreate, UserCreateByAdmin, UserUpdate, UserPasswordChange,
    UserResponse, UserListResponse, LoginRequest, TokenResponse, 
    RefreshTokenRequest, ConsentRequest
)
from app.schemas.device import (
    DeviceBase, DeviceCreate, DeviceRegister, DeviceAgentPing, DeviceUpdate,
    DeviceLockRequest, DeviceWipeRequest, DeviceResponse, DeviceListResponse,
    DeviceRegistrationResponse, DeviceLocationResponse, DeviceCommandResponse,
    CommandInfo
)
from app.schemas.location import (
    LocationHistoryResponse, LocationHistoryListResponse, LocationQuery,
    AllDevicesLocationResponse
)
from app.schemas.geofence import (
    CoordinatePoint, GeofenceBase, GeofenceCreate, GeofenceUpdate,
    GeofenceResponse, GeofenceListResponse, GeofenceCheckRequest, GeofenceCheckResponse
)
from app.schemas.alert import (
    AlertBase, AlertCreate, AlertAcknowledge, AlertResolve, AlertResponse,
    AlertWithDeviceInfo, AlertListResponse, AlertStats
)
from app.schemas.audit import (
    AuditLogCreate, AuditLogResponse, AuditLogListResponse, AuditLogQuery
)

__all__ = [
    # User
    "UserBase", "UserCreate", "UserCreateByAdmin", "UserUpdate", "UserPasswordChange",
    "UserResponse", "UserListResponse", "LoginRequest", "TokenResponse",
    "RefreshTokenRequest", "ConsentRequest",
    # Device
    "DeviceBase", "DeviceCreate", "DeviceRegister", "DeviceAgentPing", "DeviceUpdate",
    "DeviceLockRequest", "DeviceWipeRequest", "DeviceResponse", "DeviceListResponse",
    "DeviceRegistrationResponse", "DeviceLocationResponse", "DeviceCommandResponse",
    "CommandInfo",
    # Location
    "LocationHistoryResponse", "LocationHistoryListResponse", "LocationQuery",
    "AllDevicesLocationResponse",
    # Geofence
    "CoordinatePoint", "GeofenceBase", "GeofenceCreate", "GeofenceUpdate",
    "GeofenceResponse", "GeofenceListResponse", "GeofenceCheckRequest", "GeofenceCheckResponse",
    # Alert
    "AlertBase", "AlertCreate", "AlertAcknowledge", "AlertResolve", "AlertResponse",
    "AlertWithDeviceInfo", "AlertListResponse", "AlertStats",
    # Audit
    "AuditLogCreate", "AuditLogResponse", "AuditLogListResponse", "AuditLogQuery",
]
