"""
Remote Command API routes
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, Field

from app.models import get_db, User, Device, RemoteCommand, CommandType, CommandStatus, AuditAction
from app.core.security import require_admin, get_current_user
from app.services import audit_service

router = APIRouter(prefix="/commands", tags=["Remote Commands"])


# Schemas
class CommandCreate(BaseModel):
    device_id: UUID
    command_type: CommandType
    payload: Optional[str] = None
    message: Optional[str] = None


class CommandResponse(BaseModel):
    id: UUID
    device_id: UUID
    command_type: CommandType
    status: CommandStatus
    payload: Optional[str] = None
    message: Optional[str] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_data: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommandListResponse(BaseModel):
    commands: List[CommandResponse]
    total: int


@router.post("", response_model=CommandResponse, status_code=status.HTTP_201_CREATED)
async def create_command(
    command_data: CommandCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new remote command for a device.
    """
    # Verify device exists
    result = await db.execute(select(Device).where(Device.id == command_data.device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Create command
    command = RemoteCommand(
        device_id=command_data.device_id,
        command_type=command_data.command_type,
        payload=command_data.payload,
        message=command_data.message,
        created_by=current_user.id
    )
    
    db.add(command)
    
    # Log audit
    await audit_service.log_action(
        db=db,
        user=current_user,
        action=AuditAction.SETTINGS_CHANGE,
        resource_type="command",
        resource_id=str(command.id),
        details=f"Created {command_data.command_type.value} command for device {device.serial_number}",
        request=request
    )
    
    await db.commit()
    await db.refresh(command)
    
    return command


@router.get("/device/{device_id}", response_model=CommandListResponse)
async def get_device_commands(
    device_id: UUID,
    status_filter: Optional[CommandStatus] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all commands for a specific device.
    """
    query = select(RemoteCommand).where(RemoteCommand.device_id == device_id)
    
    if status_filter:
        query = query.where(RemoteCommand.status == status_filter)
    
    query = query.order_by(RemoteCommand.created_at.desc())
    
    result = await db.execute(query)
    commands = result.scalars().all()
    
    return CommandListResponse(
        commands=commands,
        total=len(commands)
    )


@router.get("/{command_id}", response_model=CommandResponse)
async def get_command(
    command_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific command by ID.
    """
    result = await db.execute(select(RemoteCommand).where(RemoteCommand.id == command_id))
    command = result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found"
        )
    
    return command


@router.delete("/{command_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_command(
    command_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a pending command.
    """
    result = await db.execute(select(RemoteCommand).where(RemoteCommand.id == command_id))
    command = result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found"
        )
    
    if command.status != CommandStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only cancel pending commands"
        )
    
    command.status = CommandStatus.CANCELLED
    
    await audit_service.log_action(
        db=db,
        user=current_user,
        action=AuditAction.SETTINGS_CHANGE,
        resource_type="command",
        resource_id=str(command.id),
        details=f"Cancelled {command.command_type.value} command",
        request=request
    )
    
    await db.commit()


# Quick action endpoints
@router.post("/lock/{device_id}", response_model=CommandResponse)
async def lock_device(
    device_id: UUID,
    request: Request,
    reason: str = "Remote lock requested",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a lock command to a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command = RemoteCommand(
        device_id=device_id,
        command_type=CommandType.LOCK,
        message=reason,
        created_by=current_user.id
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    
    return command


@router.post("/restart/{device_id}", response_model=CommandResponse)
async def restart_device(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a restart command to a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command = RemoteCommand(
        device_id=device_id,
        command_type=CommandType.RESTART,
        created_by=current_user.id
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    
    return command


@router.post("/shutdown/{device_id}", response_model=CommandResponse)
async def shutdown_device(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a shutdown command to a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command = RemoteCommand(
        device_id=device_id,
        command_type=CommandType.SHUTDOWN,
        created_by=current_user.id
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    
    return command


@router.post("/screenshot/{device_id}", response_model=CommandResponse)
async def request_screenshot(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Request a screenshot from a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command = RemoteCommand(
        device_id=device_id,
        command_type=CommandType.SCREENSHOT,
        created_by=current_user.id
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    
    return command


@router.post("/message/{device_id}", response_model=CommandResponse)
async def send_message(
    device_id: UUID,
    message: str,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to be displayed on the device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    command = RemoteCommand(
        device_id=device_id,
        command_type=CommandType.MESSAGE,
        message=message,
        created_by=current_user.id
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    
    return command


@router.get("/history/{device_id}")
async def get_command_history(
    device_id: UUID,
    limit: int = 20,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get command history for a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    query = select(RemoteCommand).where(
        RemoteCommand.device_id == device_id
    ).order_by(RemoteCommand.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    commands = result.scalars().all()
    
    return [
        {
            "id": str(cmd.id),
            "type": cmd.command_type.value,
            "status": cmd.status.value,
            "created_at": cmd.created_at.isoformat() if cmd.created_at else None,
            "executed_at": cmd.executed_at.isoformat() if cmd.executed_at else None,
            "result": cmd.result,
            "screenshot_data": cmd.screenshot_data
        }
        for cmd in commands
    ]
