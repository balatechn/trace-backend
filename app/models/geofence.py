"""
Geofence model for defining allowed zones
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.models.database import Base


class GeofenceType(str, Enum):
    CIRCLE = "circle"
    POLYGON = "polygon"


class Geofence(Base):
    __tablename__ = "geofences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Geofence type
    fence_type = Column(SQLEnum(GeofenceType), default=GeofenceType.CIRCLE)
    
    # For circle type
    center_latitude = Column(Float, nullable=True)
    center_longitude = Column(Float, nullable=True)
    radius_meters = Column(Float, nullable=True)
    
    # For polygon type (stored as JSON array of coordinates)
    polygon_coordinates = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    alert_on_exit = Column(Boolean, default=True)
    alert_on_enter = Column(Boolean, default=False)
    
    # Scope
    department = Column(String(100), nullable=True)  # If null, applies to all
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    def __repr__(self):
        return f"<Geofence {self.name}>"
