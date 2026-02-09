"""
Location history model for device tracking
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class LocationHistory(Base):
    __tablename__ = "location_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    
    # Location data
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)  # meters
    altitude = Column(Float, nullable=True)  # meters
    
    # Source of location data
    source = Column(String(50), nullable=False)  # GPS, WiFi, IP, HYBRID
    
    # Network information
    ip_address = Column(String(45), nullable=True)
    network_name = Column(String(255), nullable=True)
    
    # Metadata
    battery_level = Column(Float, nullable=True)
    is_charging = Column(String(10), nullable=True)
    
    # Timestamps
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="location_history")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_location_device_time', 'device_id', 'recorded_at'),
        Index('idx_location_coordinates', 'latitude', 'longitude'),
    )
    
    def __repr__(self):
        return f"<LocationHistory {self.device_id} at {self.recorded_at}>"
