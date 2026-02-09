"""
Pydantic schemas for Geofence API
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from app.models.geofence import GeofenceType


class CoordinatePoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class GeofenceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    fence_type: GeofenceType = GeofenceType.CIRCLE
    is_active: bool = True
    alert_on_exit: bool = True
    alert_on_enter: bool = False
    department: Optional[str] = None


class GeofenceCreate(GeofenceBase):
    # Circle type
    center_latitude: Optional[float] = Field(None, ge=-90, le=90)
    center_longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius_meters: Optional[float] = Field(None, ge=1, le=100000)
    
    # Polygon type
    polygon_coordinates: Optional[List[CoordinatePoint]] = None
    
    @model_validator(mode='after')
    def validate_geofence_data(self):
        if self.fence_type == GeofenceType.CIRCLE:
            if not all([self.center_latitude, self.center_longitude, self.radius_meters]):
                raise ValueError('Circle geofence requires center_latitude, center_longitude, and radius_meters')
        elif self.fence_type == GeofenceType.POLYGON:
            if not self.polygon_coordinates or len(self.polygon_coordinates) < 3:
                raise ValueError('Polygon geofence requires at least 3 coordinates')
        return self


class GeofenceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    alert_on_exit: Optional[bool] = None
    alert_on_enter: Optional[bool] = None
    department: Optional[str] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon_coordinates: Optional[List[CoordinatePoint]] = None


class GeofenceResponse(GeofenceBase):
    id: UUID
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon_coordinates: Optional[List[dict]] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    
    class Config:
        from_attributes = True


class GeofenceListResponse(BaseModel):
    geofences: list[GeofenceResponse]
    total: int


class GeofenceCheckRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class GeofenceCheckResponse(BaseModel):
    inside: bool
    geofence_id: UUID
    geofence_name: str
    distance_from_center: Optional[float] = None  # For circle type
