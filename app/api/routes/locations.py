"""
Location tracking routes
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import get_db, User, Device, DeviceStatus, LocationHistory
from app.schemas import (
    LocationHistoryResponse, LocationHistoryListResponse,
    DeviceLocationResponse, AllDevicesLocationResponse
)
from app.core.security import require_viewer
from app.services import audit_service
from app.models import AuditAction

router = APIRouter(prefix="/locations", tags=["Location Tracking"])


@router.get("/all", response_model=AllDevicesLocationResponse)
async def get_all_device_locations(
    request: Request,
    department: Optional[str] = None,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current locations of all devices (for map view).
    """
    query = select(Device).where(Device.last_latitude.isnot(None))
    
    if department:
        query = query.where(Device.department == department)
    
    result = await db.execute(query)
    devices = result.scalars().all()
    
    device_locations = []
    online_count = 0
    offline_count = 0
    
    for device in devices:
        device_locations.append({
            "device_id": str(device.id),
            "asset_id": device.asset_id,
            "device_name": device.device_name,
            "employee_name": device.employee_name,
            "department": device.department,
            "latitude": device.last_latitude,
            "longitude": device.last_longitude,
            "accuracy": device.last_location_accuracy,
            "location_source": device.last_location_source,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "status": device.status.value
        })
        
        if device.status == DeviceStatus.ONLINE:
            online_count += 1
        else:
            offline_count += 1
    
    # Log location access
    await audit_service.log(
        db=db,
        action=AuditAction.LOCATION_VIEW,
        user=current_user,
        request=request,
        description=f"Viewed all device locations"
    )
    await db.commit()
    
    return AllDevicesLocationResponse(
        devices=device_locations,
        total=len(device_locations),
        online_count=online_count,
        offline_count=offline_count
    )


@router.get("/{device_id}", response_model=DeviceLocationResponse)
async def get_device_location(
    device_id: UUID,
    request: Request,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current location of a specific device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Log location access
    await audit_service.log_location_access(
        db=db,
        user=current_user,
        request=request,
        device_id=device.id,
        device_identifier=device.asset_id,
        access_type="view"
    )
    await db.commit()
    
    return DeviceLocationResponse(
        device_id=device.id,
        asset_id=device.asset_id,
        device_name=device.device_name,
        employee_name=device.employee_name,
        latitude=device.last_latitude,
        longitude=device.last_longitude,
        accuracy=device.last_location_accuracy,
        location_source=device.last_location_source,
        last_seen=device.last_seen,
        status=device.status
    )


@router.get("/{device_id}/history", response_model=LocationHistoryListResponse)
async def get_device_location_history(
    device_id: UUID,
    request: Request,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get location history for a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Default to last 24 hours if no dates specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(hours=24)
    if not end_date:
        end_date = datetime.utcnow()
    
    query = select(LocationHistory).where(
        and_(
            LocationHistory.device_id == device_id,
            LocationHistory.recorded_at >= start_date,
            LocationHistory.recorded_at <= end_date
        )
    ).order_by(LocationHistory.recorded_at.desc()).limit(limit)
    
    history_result = await db.execute(query)
    locations = history_result.scalars().all()
    
    # Log history access
    await audit_service.log_location_access(
        db=db,
        user=current_user,
        request=request,
        device_id=device.id,
        device_identifier=device.asset_id,
        access_type="history"
    )
    await db.commit()
    
    return LocationHistoryListResponse(
        locations=locations,
        device_id=device_id,
        total=len(locations),
        start_date=start_date,
        end_date=end_date
    )


@router.get("/{device_id}/export")
async def export_device_location_history(
    device_id: UUID,
    request: Request,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Export location history for a device.
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    # Default to last 7 days
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=7)
    if not end_date:
        end_date = datetime.utcnow()
    
    query = select(LocationHistory).where(
        and_(
            LocationHistory.device_id == device_id,
            LocationHistory.recorded_at >= start_date,
            LocationHistory.recorded_at <= end_date
        )
    ).order_by(LocationHistory.recorded_at.asc())
    
    history_result = await db.execute(query)
    locations = history_result.scalars().all()
    
    # Log export access
    await audit_service.log_location_access(
        db=db,
        user=current_user,
        request=request,
        device_id=device.id,
        device_identifier=device.asset_id,
        access_type="export"
    )
    await db.commit()
    
    if format == "csv":
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp", "latitude", "longitude", "accuracy",
            "altitude", "source", "ip_address", "network_name"
        ])
        
        for loc in locations:
            writer.writerow([
                loc.recorded_at.isoformat(),
                loc.latitude,
                loc.longitude,
                loc.accuracy,
                loc.altitude,
                loc.source,
                loc.ip_address,
                loc.network_name
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=location_history_{device.asset_id}_{start_date.date()}_{end_date.date()}.csv"
            }
        )
    
    return {
        "device_id": str(device_id),
        "asset_id": device.asset_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_records": len(locations),
        "locations": [
            {
                "timestamp": loc.recorded_at.isoformat(),
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "accuracy": loc.accuracy,
                "altitude": loc.altitude,
                "source": loc.source,
                "ip_address": loc.ip_address,
                "network_name": loc.network_name
            }
            for loc in locations
        ]
    }
