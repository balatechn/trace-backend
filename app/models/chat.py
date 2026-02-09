"""
Chat/Message model for device communication
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base


class MessageDirection(str, Enum):
    TO_DEVICE = "to_device"      # Admin to device user
    FROM_DEVICE = "from_device"  # Device user to admin


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    
    direction = Column(SQLEnum(MessageDirection), nullable=False)
    message = Column(Text, nullable=False)
    
    # Sender info
    sender_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Admin user
    sender_name = Column(String(255), nullable=True)  # Display name
    
    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", backref="chat_messages")
    sender = relationship("User", backref="sent_messages")
