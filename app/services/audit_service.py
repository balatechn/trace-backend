"""
Audit logging service for tracking all actions
"""
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import AuditLog, AuditAction, User


class AuditService:
    """Service for creating and managing audit logs"""
    
    @staticmethod
    def get_client_ip(request: Request) -> Optional[str]:
        """Extract client IP from request"""
        # Check forwarded headers first (for reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return None
    
    @staticmethod
    def get_user_agent(request: Request) -> Optional[str]:
        """Extract user agent from request"""
        return request.headers.get("User-Agent", "")[:500]
    
    async def log(
        self,
        db: AsyncSession,
        action: AuditAction,
        user: Optional[User] = None,
        request: Optional[Request] = None,
        target_type: Optional[str] = None,
        target_id: Optional[UUID] = None,
        target_identifier: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[dict] = None
    ) -> AuditLog:
        """Create an audit log entry"""
        
        log_entry = AuditLog(
            action=action,
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_role=user.role.value if user else None,
            target_type=target_type,
            target_id=target_id,
            target_identifier=target_identifier,
            description=description,
            details=details,
            ip_address=self.get_client_ip(request) if request else None,
            user_agent=self.get_user_agent(request) if request else None
        )
        
        db.add(log_entry)
        await db.flush()
        
        return log_entry
    
    async def log_login(
        self,
        db: AsyncSession,
        user: User,
        request: Request,
        success: bool = True
    ) -> AuditLog:
        """Log a login attempt"""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        return await self.log(
            db=db,
            action=action,
            user=user if success else None,
            request=request,
            target_type="user",
            target_id=user.id,
            target_identifier=user.email,
            description=f"{'Successful' if success else 'Failed'} login attempt"
        )
    
    async def log_device_action(
        self,
        db: AsyncSession,
        action: AuditAction,
        user: User,
        request: Request,
        device_id: UUID,
        device_identifier: str,
        description: str,
        details: Optional[dict] = None
    ) -> AuditLog:
        """Log a device-related action"""
        return await self.log(
            db=db,
            action=action,
            user=user,
            request=request,
            target_type="device",
            target_id=device_id,
            target_identifier=device_identifier,
            description=description,
            details=details
        )
    
    async def log_location_access(
        self,
        db: AsyncSession,
        user: User,
        request: Request,
        device_id: UUID,
        device_identifier: str,
        access_type: str = "view"  # view, history, export
    ) -> AuditLog:
        """Log access to device location data"""
        action_map = {
            "view": AuditAction.LOCATION_VIEW,
            "history": AuditAction.LOCATION_HISTORY_VIEW,
            "export": AuditAction.LOCATION_EXPORT
        }
        return await self.log(
            db=db,
            action=action_map.get(access_type, AuditAction.LOCATION_VIEW),
            user=user,
            request=request,
            target_type="device",
            target_id=device_id,
            target_identifier=device_identifier,
            description=f"Location {access_type} for device {device_identifier}"
        )


audit_service = AuditService()
