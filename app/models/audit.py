"""
Audit log model for tracking all access and actions
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class AuditAction(str, Enum):
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    
    # Device Management
    DEVICE_CREATE = "device_create"
    DEVICE_UPDATE = "device_update"
    DEVICE_DELETE = "device_delete"
    DEVICE_REGISTER = "device_register"
    DEVICE_LOCK = "device_lock"
    DEVICE_UNLOCK = "device_unlock"
    DEVICE_WIPE = "device_wipe"
    
    # Location Tracking
    LOCATION_VIEW = "location_view"
    LOCATION_HISTORY_VIEW = "location_history_view"
    LOCATION_EXPORT = "location_export"
    
    # Geofence
    GEOFENCE_CREATE = "geofence_create"
    GEOFENCE_UPDATE = "geofence_update"
    GEOFENCE_DELETE = "geofence_delete"
    
    # User Management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_ROLE_CHANGE = "user_role_change"
    
    # Alert Management
    ALERT_ACKNOWLEDGE = "alert_acknowledge"
    ALERT_RESOLVE = "alert_resolve"
    
    # System
    SETTINGS_CHANGE = "settings_change"
    DATA_EXPORT = "data_export"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Who performed the action
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = Column(String(255), nullable=True)  # Denormalized for historical record
    user_role = Column(String(50), nullable=True)
    
    # What action was performed
    action = Column(SQLEnum(AuditAction), nullable=False)
    
    # Target of the action
    target_type = Column(String(50), nullable=True)  # device, user, geofence, etc.
    target_id = Column(UUID(as_uuid=True), nullable=True)
    target_identifier = Column(String(255), nullable=True)  # Human-readable identifier
    
    # Details
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional structured data
    
    # Context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_email} at {self.created_at}>"
