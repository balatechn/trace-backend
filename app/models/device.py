"""
Device model for laptop asset tracking
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, Float, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    LOCKED = "locked"
    WIPED = "wiped"


class DeviceType(str, Enum):
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    MOBILE = "mobile"
    WORKSTATION = "workstation"


class Device(Base):
    __tablename__ = "devices"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    asset_id = Column(String(50), unique=True, index=True, nullable=False)
    device_name = Column(String(255), nullable=True)
    device_type = Column(SQLEnum(DeviceType), default=DeviceType.LAPTOP)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    os_name = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    
    # Mobile Device Fields
    imei = Column(String(20), nullable=True, index=True)  # IMEI number for mobile
    imei2 = Column(String(20), nullable=True)  # Second IMEI for dual-SIM
    phone_number = Column(String(20), nullable=True)
    carrier = Column(String(50), nullable=True)  # Mobile carrier
    
    # Assignment
    employee_name = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Status and Tracking
    status = Column(SQLEnum(DeviceStatus), default=DeviceStatus.OFFLINE)
    is_registered = Column(Boolean, default=False)
    agent_installed = Column(Boolean, default=False)
    agent_version = Column(String(20), nullable=True)
    
    # Location
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_location_accuracy = Column(Float, nullable=True)
    last_location_source = Column(String(50), nullable=True)  # GPS, WiFi, IP
    last_ip_address = Column(String(45), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    
    # Network
    mac_address = Column(String(17), nullable=True)
    network_name = Column(String(255), nullable=True)
    
    # Security
    is_encrypted = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    lock_reason = Column(Text, nullable=True)
    is_wiped = Column(Boolean, default=False)
    
    # Agent Token (hashed)
    agent_token_hash = Column(String(255), nullable=True)
    
    # Consent
    consent_given = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime, nullable=True)
    policy_accepted = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    registered_at = Column(DateTime, nullable=True)
    
    # Relationships
    assigned_user = relationship("User", back_populates="devices")
    location_history = relationship("LocationHistory", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Device {self.asset_id} - {self.serial_number}>"
