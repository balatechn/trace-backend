"""
Alert management routes
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import get_db, User, Alert, Device, AlertType, AlertSeverity, AuditAction
from app.schemas import (
    AlertAcknowledge, AlertResolve, AlertResponse,
    AlertWithDeviceInfo, AlertListResponse, AlertStats
)
from app.core.security import require_admin, require_viewer
from app.services import audit_service

router = APIRouter(prefix="/alerts", tags=["Alert Management"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    alert_type: Optional[AlertType] = None,
    severity: Optional[AlertSeverity] = None,
    is_acknowledged: Optional[bool] = None,
    is_resolved: Optional[bool] = None,
    device_id: Optional[UUID] = None,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    List all alerts with filtering and pagination.
    """
    query = select(Alert)
    count_query = select(func.count(Alert.id))
    
    # Apply filters
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
        count_query = count_query.where(Alert.alert_type == alert_type)
    if severity:
        query = query.where(Alert.severity == severity)
        count_query = count_query.where(Alert.severity == severity)
    if is_acknowledged is not None:
        query = query.where(Alert.is_acknowledged == is_acknowledged)
        count_query = count_query.where(Alert.is_acknowledged == is_acknowledged)
    if is_resolved is not None:
        query = query.where(Alert.is_resolved == is_resolved)
        count_query = count_query.where(Alert.is_resolved == is_resolved)
    if device_id:
        query = query.where(Alert.device_id == device_id)
        count_query = count_query.where(Alert.device_id == device_id)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get unacknowledged count
    unack_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.is_acknowledged == False)
    )
    unacknowledged = unack_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(Alert.created_at.desc())
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    # Enrich with device info
    enriched_alerts = []
    for alert in alerts:
        device_result = await db.execute(
            select(Device).where(Device.id == alert.device_id)
        )
        device = device_result.scalar_one_or_none()
        
        alert_dict = {
            "id": alert.id,
            "device_id": alert.device_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "latitude": alert.latitude,
            "longitude": alert.longitude,
            "geofence_id": alert.geofence_id,
            "is_acknowledged": alert.is_acknowledged,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at": alert.acknowledged_at,
            "is_resolved": alert.is_resolved,
            "resolved_at": alert.resolved_at,
            "notes": alert.notes,
            "created_at": alert.created_at,
            "device_asset_id": device.asset_id if device else None,
            "device_name": device.device_name if device else None,
            "employee_name": device.employee_name if device else None
        }
        enriched_alerts.append(AlertWithDeviceInfo(**alert_dict))
    
    return AlertListResponse(
        alerts=enriched_alerts,
        total=total,
        unacknowledged_count=unacknowledged,
        page=page,
        per_page=per_page
    )


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get alert statistics.
    """
    total_result = await db.execute(select(func.count(Alert.id)))
    total = total_result.scalar()
    
    unack_result = await db.execute(
        select(func.count(Alert.id)).where(Alert.is_acknowledged == False)
    )
    unacknowledged = unack_result.scalar()
    
    # By severity
    severity_result = await db.execute(
        select(Alert.severity, func.count(Alert.id))
        .where(Alert.is_resolved == False)
        .group_by(Alert.severity)
    )
    by_severity = {sev.value: count for sev, count in severity_result.all()}
    
    # By type
    type_result = await db.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(Alert.is_resolved == False)
        .group_by(Alert.alert_type)
    )
    by_type = {t.value: count for t, count in type_result.all()}
    
    return AlertStats(
        total=total,
        unacknowledged=unacknowledged,
        by_severity=by_severity,
        by_type=by_type
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific alert by ID.
    """
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    return alert


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    ack_data: AlertAcknowledge,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Acknowledge an alert.
    """
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    if alert.is_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert already acknowledged"
        )
    
    alert.is_acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.utcnow()
    if ack_data.notes:
        alert.notes = ack_data.notes
    
    await audit_service.log(
        db=db,
        action=AuditAction.ALERT_ACKNOWLEDGE,
        user=current_user,
        request=request,
        target_type="alert",
        target_id=alert.id,
        description=f"Acknowledged alert: {alert.title}"
    )
    
    await db.commit()
    
    return {"message": "Alert acknowledged", "acknowledged_at": alert.acknowledged_at}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    resolve_data: AlertResolve,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve an alert.
    """
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    if alert.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert already resolved"
        )
    
    # Auto-acknowledge if not already
    if not alert.is_acknowledged:
        alert.is_acknowledged = True
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    if resolve_data.notes:
        alert.notes = (alert.notes or "") + f"\nResolution: {resolve_data.notes}"
    
    await audit_service.log(
        db=db,
        action=AuditAction.ALERT_RESOLVE,
        user=current_user,
        request=request,
        target_type="alert",
        target_id=alert.id,
        description=f"Resolved alert: {alert.title}"
    )
    
    await db.commit()
    
    return {"message": "Alert resolved", "resolved_at": alert.resolved_at}
