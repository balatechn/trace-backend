"""
Device agent routes for registration and location pings
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import get_db, Device, DeviceStatus, DeviceType, LocationHistory
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
    
    # Build response with any pending commands
    response = DeviceCommandResponse()
    
    if device.is_wiped:
        response.command = "wipe"
        response.message = "Remote wipe requested"
    elif device.is_locked:
        response.command = "lock"
        response.message = device.lock_reason or "Device lock requested"
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
