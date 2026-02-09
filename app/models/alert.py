"""
Alert model for geofence violations and security events
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class AlertType(str, Enum):
    GEOFENCE_EXIT = "geofence_exit"
    GEOFENCE_ENTER = "geofence_enter"
    DEVICE_OFFLINE = "device_offline"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    AGENT_TAMPER = "agent_tamper"
    LOCK_REQUESTED = "lock_requested"
    WIPE_REQUESTED = "wipe_requested"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    
    # Alert details
    alert_type = Column(SQLEnum(AlertType), nullable=False)
    severity = Column(SQLEnum(AlertSeverity), default=AlertSeverity.MEDIUM)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    
    # Location at time of alert
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Related geofence
    geofence_id = Column(UUID(as_uuid=True), ForeignKey("geofences.id", ondelete="SET NULL"), nullable=True)
    
    # Status
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(UUID(as_uuid=True), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    device = relationship("Device", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert {self.alert_type} for {self.device_id}>"
