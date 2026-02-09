"""
Audit log routes
"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import get_db, User, AuditLog, AuditAction
from app.schemas import AuditLogResponse, AuditLogListResponse
from app.core.security import require_admin

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    action: Optional[AuditAction] = None,
    user_id: Optional[UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List audit logs with filtering and pagination.
    Requires IT Admin or Super Admin role.
    """
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    
    # Apply filters
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if target_id:
        filters.append(AuditLog.target_id == target_id)
    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(AuditLog.created_at.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/summary")
async def get_audit_summary(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit log summary for the specified period.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total logs in period
    total_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= start_date)
    )
    total = total_result.scalar()
    
    # By action type
    action_result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.action)
    )
    by_action = {action.value: count for action, count in action_result.all()}
    
    # By user
    user_result = await db.execute(
        select(AuditLog.user_email, func.count(AuditLog.id))
        .where(AuditLog.created_at >= start_date)
        .group_by(AuditLog.user_email)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    top_users = {email or "System": count for email, count in user_result.all()}
    
    # Login attempts
    login_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.action == AuditAction.LOGIN,
                AuditLog.created_at >= start_date
            )
        )
    )
    logins = login_result.scalar()
    
    failed_login_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.action == AuditAction.LOGIN_FAILED,
                AuditLog.created_at >= start_date
            )
        )
    )
    failed_logins = failed_login_result.scalar()
    
    return {
        "period_days": days,
        "total_events": total,
        "by_action": by_action,
        "top_users": top_users,
        "login_attempts": logins,
        "failed_logins": failed_logins
    }


@router.get("/device/{device_id}")
async def get_device_audit_logs(
    device_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs for a specific device.
    """
    query = select(AuditLog).where(
        and_(
            AuditLog.target_type == "device",
            AuditLog.target_id == device_id
        )
    )
    count_query = select(func.count(AuditLog.id)).where(
        and_(
            AuditLog.target_type == "device",
            AuditLog.target_id == device_id
        )
    )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(AuditLog.created_at.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/user/{user_id}")
async def get_user_audit_logs(
    user_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs for a specific user's actions.
    """
    query = select(AuditLog).where(AuditLog.user_id == user_id)
    count_query = select(func.count(AuditLog.id)).where(AuditLog.user_id == user_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(AuditLog.created_at.desc())
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        per_page=per_page
    )
