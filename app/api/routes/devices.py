"""
Device management routes
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import get_db, User, Device, DeviceStatus, AuditAction, Alert, AlertType, AlertSeverity
from app.schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, DeviceListResponse,
    DeviceLockRequest, DeviceWipeRequest
)
from app.core.security import require_admin, require_viewer, get_current_user
from app.services import audit_service
from app.core.config import settings

router = APIRouter(prefix="/devices", tags=["Device Management"])


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[DeviceStatus] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    List all devices with filtering and pagination.
    """
    query = select(Device)
    count_query = select(func.count(Device.id))
    
    # Apply filters
    if status:
        query = query.where(Device.status == status)
        count_query = count_query.where(Device.status == status)
    if department:
        query = query.where(Device.department == department)
        count_query = count_query.where(Device.department == department)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Device.serial_number.ilike(search_filter)) |
            (Device.asset_id.ilike(search_filter)) |
            (Device.device_name.ilike(search_filter)) |
            (Device.employee_name.ilike(search_filter))
        )
        count_query = count_query.where(
            (Device.serial_number.ilike(search_filter)) |
            (Device.asset_id.ilike(search_filter)) |
            (Device.device_name.ilike(search_filter)) |
            (Device.employee_name.ilike(search_filter))
        )
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get online/offline counts
    online_result = await db.execute(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
    )
    online_count = online_result.scalar() or 0
    
    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Device.last_seen.desc().nullslast())
    
    result = await db.execute(query)
    devices = result.scalars().all()
    
    return DeviceListResponse(
        devices=devices,
        total=total,
        online_count=online_count,
        offline_count=total - online_count,
        page=page,
        per_page=per_page
    )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific device by ID.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    return device


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    device_data: DeviceCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new device in the system.
    """
    # Check for duplicate serial number or asset ID
    result = await db.execute(
        select(Device).where(
            (Device.serial_number == device_data.serial_number) |
            (Device.asset_id == device_data.asset_id)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device with this serial number or asset ID already exists"
        )
    
    device = Device(**device_data.model_dump())
    db.add(device)
    await db.flush()
    
    await audit_service.log(
        db=db,
        action=AuditAction.DEVICE_CREATE,
        user=current_user,
        request=request,
        target_type="device",
        target_id=device.id,
        target_identifier=device.asset_id,
        description=f"Created device {device.asset_id}"
    )
    
    await db.commit()
    await db.refresh(device)
    
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    device_data: DeviceUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update device information.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    changes = {}
    update_data = device_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if getattr(device, field) != value:
            changes[field] = {"old": str(getattr(device, field)), "new": str(value)}
            setattr(device, field, value)
    
    if changes:
        await audit_service.log(
            db=db,
            action=AuditAction.DEVICE_UPDATE,
            user=current_user,
            request=request,
            target_type="device",
            target_id=device.id,
            target_identifier=device.asset_id,
            description=f"Updated device {device.asset_id}",
            details=changes
        )
    
    await db.commit()
    await db.refresh(device)
    
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a device and all its associated data.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    await audit_service.log(
        db=db,
        action=AuditAction.DEVICE_DELETE,
        user=current_user,
        request=request,
        target_type="device",
        target_id=device.id,
        target_identifier=device.asset_id,
        description=f"Deleted device {device.asset_id}"
    )
    
    await db.delete(device)
    await db.commit()


@router.post("/{device_id}/lock")
async def lock_device(
    device_id: UUID,
    lock_data: DeviceLockRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Request to lock a device remotely.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.is_locked = True
    device.lock_reason = lock_data.reason
    device.status = DeviceStatus.LOCKED
    
    # Create alert
    alert = Alert(
        device_id=device.id,
        alert_type=AlertType.LOCK_REQUESTED,
        severity=AlertSeverity.HIGH,
        title=f"Lock requested for {device.asset_id}",
        message=lock_data.reason
    )
    db.add(alert)
    
    await audit_service.log(
        db=db,
        action=AuditAction.DEVICE_LOCK,
        user=current_user,
        request=request,
        target_type="device",
        target_id=device.id,
        target_identifier=device.asset_id,
        description=f"Lock requested: {lock_data.reason}"
    )
    
    await db.commit()
    
    return {"message": f"Lock command sent to device {device.asset_id}"}


@router.post("/{device_id}/unlock")
async def unlock_device(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Unlock a previously locked device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.is_locked = False
    device.lock_reason = None
    if device.last_seen and device.last_seen > datetime.utcnow() - timedelta(minutes=10):
        device.status = DeviceStatus.ONLINE
    else:
        device.status = DeviceStatus.OFFLINE
    
    await audit_service.log(
        db=db,
        action=AuditAction.DEVICE_UNLOCK,
        user=current_user,
        request=request,
        target_type="device",
        target_id=device.id,
        target_identifier=device.asset_id,
        description="Device unlocked"
    )
    
    await db.commit()
    
    return {"message": f"Device {device.asset_id} unlocked"}


@router.post("/{device_id}/wipe")
async def wipe_device(
    device_id: UUID,
    wipe_data: DeviceWipeRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Request to wipe a device remotely (requires confirmation).
    """
    if not wipe_data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wipe operation requires explicit confirmation"
        )
    
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.is_wiped = True
    device.status = DeviceStatus.WIPED
    
    # Create critical alert
    alert = Alert(
        device_id=device.id,
        alert_type=AlertType.WIPE_REQUESTED,
        severity=AlertSeverity.CRITICAL,
        title=f"WIPE requested for {device.asset_id}",
        message=wipe_data.reason
    )
    db.add(alert)
    
    await audit_service.log(
        db=db,
        action=AuditAction.DEVICE_WIPE,
        user=current_user,
        request=request,
        target_type="device",
        target_id=device.id,
        target_identifier=device.asset_id,
        description=f"WIPE requested: {wipe_data.reason}",
        details={"reason": wipe_data.reason}
    )
    
    await db.commit()
    
    return {"message": f"Wipe command sent to device {device.asset_id}", "warning": "This action cannot be undone"}


@router.get("/stats/summary")
async def get_device_stats(
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get device statistics summary.
    """
    total_result = await db.execute(select(func.count(Device.id)))
    total = total_result.scalar()
    
    online_result = await db.execute(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.ONLINE)
    )
    online = online_result.scalar()
    
    offline_result = await db.execute(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.OFFLINE)
    )
    offline = offline_result.scalar()
    
    locked_result = await db.execute(
        select(func.count(Device.id)).where(Device.is_locked == True)
    )
    locked = locked_result.scalar()
    
    # Get department breakdown
    dept_result = await db.execute(
        select(Device.department, func.count(Device.id))
        .group_by(Device.department)
    )
    by_department = {dept or "Unassigned": count for dept, count in dept_result.all()}
    
    return {
        "total": total,
        "online": online,
        "offline": offline,
        "locked": locked,
        "by_department": by_department
    }
