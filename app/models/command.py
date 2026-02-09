"""
Remote Command model for device management
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class CommandType(str, Enum):
    LOCK = "lock"
    UNLOCK = "unlock"
    RESTART = "restart"
    SHUTDOWN = "shutdown"
    SCREENSHOT = "screenshot"
    MESSAGE = "message"
    EXECUTE = "execute"  # Run custom command


class CommandStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RemoteCommand(Base):
    __tablename__ = "remote_commands"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    
    command_type = Column(SQLEnum(CommandType), nullable=False)
    status = Column(SQLEnum(CommandStatus), default=CommandStatus.PENDING)
    
    # Command payload (JSON string for complex commands)
    payload = Column(Text, nullable=True)
    
    # For messages
    message = Column(Text, nullable=True)
    
    # Result/response from agent
    result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Screenshot data (base64 or URL)
    screenshot_data = Column(Text, nullable=True)
    
    # Tracking
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    
    # Relationships
    device = relationship("Device", backref="commands")
    creator = relationship("User", backref="commands_created")
