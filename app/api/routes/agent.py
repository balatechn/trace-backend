"""
Device agent routes for registration and location pings
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import get_db, Device, DeviceStatus, DeviceType, LocationHistory, RemoteCommand, CommandStatus, CommandType
from app.schemas import (
    DeviceRegister, DeviceAgentPing, DeviceRegistrationResponse,
    DeviceCommandResponse
)
from app.core.security import create_agent_token, verify_agent_token, get_password_hash
from app.services import geofence_service

router = APIRouter(prefix="/agent", tags=["Device Agent"])


@router.post("/register", response_model=DeviceRegistrationResponse)
async def register_agent(
    registration: DeviceRegister,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a device agent with the server.
    Auto-creates device if not pre-registered.
    """
    # Find existing device by serial number
    result = await db.execute(
        select(Device).where(Device.serial_number == registration.serial_number)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        # Auto-create device if not exists
        device = Device(
            serial_number=registration.serial_number,
            asset_id=registration.asset_id or f"AUTO-{registration.serial_number}",
            device_name=registration.device_name or f"Device-{registration.serial_number}",
            device_type=DeviceType.LAPTOP,
            status=DeviceStatus.OFFLINE
        )
        db.add(device)
        await db.flush()  # Get the device ID
    
    if device.is_registered and device.agent_installed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device already registered"
        )
    
    # Update device information
    device.device_name = registration.device_name or device.device_name
    device.manufacturer = registration.manufacturer or device.manufacturer
    device.model = registration.model or device.model
    device.os_name = registration.os_name
    device.os_version = registration.os_version
    device.mac_address = registration.mac_address
    device.agent_version = registration.agent_version
    device.agent_installed = True
    device.is_registered = True
    device.registered_at = datetime.utcnow()
    device.status = DeviceStatus.ONLINE
    device.last_seen = datetime.utcnow()
    
    # Generate agent token
    agent_token = create_agent_token(str(device.id))
    device.agent_token_hash = get_password_hash(agent_token[:32])  # Store partial hash
    
    await db.commit()
    
    return DeviceRegistrationResponse(
        device_id=device.id,
        agent_token=agent_token,
        message="Device registered successfully. Store the token securely."
    )


@router.post("/ping", response_model=DeviceCommandResponse)
async def agent_ping(
    ping_data: DeviceAgentPing,
    request: Request,
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Receive location ping from device agent.
    Returns any pending commands for the device.
    """
    device_id = agent_payload.get("device_id")
    
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Update device status
    device.status = DeviceStatus.ONLINE
    device.last_seen = datetime.utcnow()
    device.agent_version = ping_data.agent_version
    
    # Update network info
    if ping_data.ip_address:
        device.last_ip_address = ping_data.ip_address
    if ping_data.network_name:
        device.network_name = ping_data.network_name
    
    # Update location if provided
    if ping_data.latitude is not None and ping_data.longitude is not None:
        device.last_latitude = ping_data.latitude
        device.last_longitude = ping_data.longitude
        device.last_location_accuracy = ping_data.accuracy
        device.last_location_source = ping_data.location_source
        
        # Store location history
        location = LocationHistory(
            device_id=device.id,
            latitude=ping_data.latitude,
            longitude=ping_data.longitude,
            accuracy=ping_data.accuracy,
            altitude=ping_data.altitude,
            source=ping_data.location_source,
            ip_address=ping_data.ip_address,
            network_name=ping_data.network_name,
            battery_level=ping_data.battery_level,
            is_charging=str(ping_data.is_charging) if ping_data.is_charging is not None else None
        )
        db.add(location)
        
        # Check geofences
        await geofence_service.check_all_geofences(
            db, device, ping_data.latitude, ping_data.longitude
        )
    
    await db.commit()
    
    # Check for pending remote commands
    cmd_result = await db.execute(
        select(RemoteCommand)
        .where(RemoteCommand.device_id == device.id)
        .where(RemoteCommand.status == CommandStatus.PENDING)
        .order_by(RemoteCommand.created_at.asc())
        .limit(5)  # Get up to 5 pending commands
    )
    pending_commands = cmd_result.scalars().all()
    
    # Build response with any pending commands
    from app.schemas.device import CommandInfo
    response = DeviceCommandResponse()
    commands_list = []
    
    for pending_command in pending_commands:
        # Mark command as sent
        pending_command.status = CommandStatus.SENT
        pending_command.sent_at = datetime.utcnow()
        
        # Build payload for the command
        payload = {}
        if pending_command.payload:
            import json
            try:
                payload = json.loads(pending_command.payload)
            except:
                pass
        if pending_command.message:
            payload['message'] = pending_command.message
        
        commands_list.append(CommandInfo(
            id=str(pending_command.id),
            type=pending_command.command_type.value,
            payload=payload if payload else None
        ))
    
    if pending_commands:
        await db.commit()
    
    # Also check legacy lock/wipe flags
    if device.is_wiped:
        commands_list.append(CommandInfo(type="wipe", payload={"message": "Remote wipe requested"}))
    elif device.is_locked and not any(c.type == "lock" for c in commands_list):
        commands_list.append(CommandInfo(type="lock", payload={"message": device.lock_reason or "Device lock requested"}))
    
    response.commands = commands_list if commands_list else None
    
    # Also populate legacy single command field for backward compatibility
    if commands_list:
        response.command = commands_list[0].type
        response.command_id = commands_list[0].id
        response.message = commands_list[0].payload.get('message') if commands_list[0].payload else None
    else:
        response.command = None
    
    return response


@router.post("/consent")
async def record_consent(
    request: Request,
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Record user consent from device agent.
    """
    device_id = agent_payload.get("device_id")
    
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.consent_given = True
    device.consent_timestamp = datetime.utcnow()
    device.policy_accepted = True
    
    await db.commit()
    
    return {"message": "Consent recorded", "timestamp": device.consent_timestamp}


@router.get("/status")
async def get_agent_status(
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current device status and any pending commands.
    """
    device_id = agent_payload.get("device_id")
    
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return {
        "device_id": str(device.id),
        "asset_id": device.asset_id,
        "status": device.status.value,
        "is_locked": device.is_locked,
        "is_wiped": device.is_wiped,
        "lock_reason": device.lock_reason,
        "consent_required": not device.consent_given,
        "server_time": datetime.utcnow().isoformat()
    }


from pydantic import BaseModel
from typing import Optional

class CommandResultData(BaseModel):
    command_id: str
    status: str  # executed, failed
    result: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_data: Optional[str] = None  # Base64 encoded screenshot


@router.post("/command-result")
async def report_command_result(
    result_data: CommandResultData,
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Report the result of a command execution.
    """
    device_id = agent_payload.get("device_id")
    
    # Find the command
    cmd_result = await db.execute(
        select(RemoteCommand).where(RemoteCommand.id == result_data.command_id)
    )
    command = cmd_result.scalar_one_or_none()
    
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found"
        )
    
    if str(command.device_id) != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Command does not belong to this device"
        )
    
    # Update command status
    if result_data.status == "executed":
        command.status = CommandStatus.EXECUTED
    else:
        command.status = CommandStatus.FAILED
    
    command.executed_at = datetime.utcnow()
    command.result = result_data.result
    command.error_message = result_data.error_message
    command.screenshot_data = result_data.screenshot_data
    
    await db.commit()
    
    return {"message": "Command result recorded"}


class ScreenshotUpload(BaseModel):
    screenshot: str  # Base64 encoded screenshot
    timestamp: Optional[str] = None
    command_id: Optional[str] = None  # If responding to a screenshot command


@router.post("/screenshot")
async def upload_screenshot(
    screenshot_data: ScreenshotUpload,
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a screenshot from the device.
    """
    device_id = agent_payload.get("device_id")
    
    # Get device
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # If this is for a specific command, update that command
    if screenshot_data.command_id:
        cmd_result = await db.execute(
            select(RemoteCommand)
            .where(RemoteCommand.id == screenshot_data.command_id)
            .where(RemoteCommand.device_id == device_id)
        )
        command = cmd_result.scalar_one_or_none()
        
        if command:
            command.status = CommandStatus.EXECUTED
            command.executed_at = datetime.utcnow()
            command.screenshot_data = screenshot_data.screenshot
            command.result = f"Screenshot captured at {screenshot_data.timestamp or datetime.utcnow().isoformat()}"
    else:
        # Create a new screenshot command record to store this
        from app.models import CommandType
        new_cmd = RemoteCommand(
            device_id=device.id,
            command_type=CommandType.SCREENSHOT,
            status=CommandStatus.EXECUTED,
            executed_at=datetime.utcnow(),
            screenshot_data=screenshot_data.screenshot,
            result=f"Screenshot captured at {screenshot_data.timestamp or datetime.utcnow().isoformat()}"
        )
        db.add(new_cmd)
    
    await db.commit()
    
    return {"message": "Screenshot uploaded successfully"}


@router.post("/chat")
async def send_chat_message(
    message: str,
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a chat message from the device to admins.
    """
    from app.models import ChatMessage, MessageDirection
    
    device_id = agent_payload.get("device_id")
    
    # Get device info
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    chat_msg = ChatMessage(
        device_id=device.id,
        direction=MessageDirection.FROM_DEVICE,
        message=message,
        sender_name=device.employee_name or device.device_name or "Device User"
    )
    db.add(chat_msg)
    await db.commit()
    
    return {"message": "Message sent", "id": str(chat_msg.id)}


@router.get("/chat/messages")
async def get_chat_messages(
    agent_payload: dict = Depends(verify_agent_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Get pending chat messages for the device.
    """
    from app.models import ChatMessage, MessageDirection
    
    device_id = agent_payload.get("device_id")
    
    # Get unread messages to device
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.device_id == device_id)
        .where(ChatMessage.direction == MessageDirection.TO_DEVICE)
        .where(ChatMessage.is_read == False)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    # Mark as read
    for msg in messages:
        msg.is_read = True
        msg.read_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "messages": [
            {
                "id": str(m.id),
                "message": m.message,
                "sender_name": m.sender_name or "Admin",
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    }
