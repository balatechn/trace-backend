"""
Geofence management routes
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import get_db, User, Geofence, AuditAction
from app.schemas import (
    GeofenceCreate, GeofenceUpdate, GeofenceResponse, GeofenceListResponse,
    GeofenceCheckRequest, GeofenceCheckResponse
)
from app.core.security import require_admin, require_viewer
from app.services import audit_service, geofence_service

router = APIRouter(prefix="/geofences", tags=["Geofence Management"])


@router.get("", response_model=GeofenceListResponse)
async def list_geofences(
    is_active: Optional[bool] = None,
    department: Optional[str] = None,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    List all geofences.
    """
    query = select(Geofence)
    
    if is_active is not None:
        query = query.where(Geofence.is_active == is_active)
    if department:
        query = query.where(
            (Geofence.department == None) | (Geofence.department == department)
        )
    
    query = query.order_by(Geofence.created_at.desc())
    
    result = await db.execute(query)
    geofences = result.scalars().all()
    
    return GeofenceListResponse(
        geofences=geofences,
        total=len(geofences)
    )


@router.get("/{geofence_id}", response_model=GeofenceResponse)
async def get_geofence(
    geofence_id: UUID,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific geofence by ID.
    """
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    geofence = result.scalar_one_or_none()
    
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    return geofence


@router.post("", response_model=GeofenceResponse, status_code=status.HTTP_201_CREATED)
async def create_geofence(
    geofence_data: GeofenceCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new geofence.
    """
    geofence_dict = geofence_data.model_dump()
    
    # Convert polygon coordinates to list of dicts
    if geofence_dict.get("polygon_coordinates"):
        geofence_dict["polygon_coordinates"] = [
            {"latitude": p.latitude, "longitude": p.longitude}
            for p in geofence_data.polygon_coordinates
        ]
    
    geofence = Geofence(**geofence_dict, created_by=current_user.id)
    db.add(geofence)
    await db.flush()
    
    await audit_service.log(
        db=db,
        action=AuditAction.GEOFENCE_CREATE,
        user=current_user,
        request=request,
        target_type="geofence",
        target_id=geofence.id,
        target_identifier=geofence.name,
        description=f"Created geofence '{geofence.name}'"
    )
    
    await db.commit()
    await db.refresh(geofence)
    
    return geofence


@router.patch("/{geofence_id}", response_model=GeofenceResponse)
async def update_geofence(
    geofence_id: UUID,
    geofence_data: GeofenceUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a geofence.
    """
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    geofence = result.scalar_one_or_none()
    
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    update_data = geofence_data.model_dump(exclude_unset=True)
    
    # Convert polygon coordinates
    if "polygon_coordinates" in update_data and update_data["polygon_coordinates"]:
        update_data["polygon_coordinates"] = [
            {"latitude": p.latitude, "longitude": p.longitude}
            for p in geofence_data.polygon_coordinates
        ]
    
    changes = {}
    for field, value in update_data.items():
        if getattr(geofence, field) != value:
            changes[field] = {"old": str(getattr(geofence, field)), "new": str(value)}
            setattr(geofence, field, value)
    
    if changes:
        await audit_service.log(
            db=db,
            action=AuditAction.GEOFENCE_UPDATE,
            user=current_user,
            request=request,
            target_type="geofence",
            target_id=geofence.id,
            target_identifier=geofence.name,
            description=f"Updated geofence '{geofence.name}'",
            details=changes
        )
    
    await db.commit()
    await db.refresh(geofence)
    
    return geofence


@router.delete("/{geofence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geofence(
    geofence_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a geofence.
    """
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    geofence = result.scalar_one_or_none()
    
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    await audit_service.log(
        db=db,
        action=AuditAction.GEOFENCE_DELETE,
        user=current_user,
        request=request,
        target_type="geofence",
        target_id=geofence.id,
        target_identifier=geofence.name,
        description=f"Deleted geofence '{geofence.name}'"
    )
    
    await db.delete(geofence)
    await db.commit()


@router.post("/{geofence_id}/check", response_model=GeofenceCheckResponse)
async def check_point_in_geofence(
    geofence_id: UUID,
    check_data: GeofenceCheckRequest,
    current_user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if a point is inside a specific geofence.
    """
    result = await db.execute(select(Geofence).where(Geofence.id == geofence_id))
    geofence = result.scalar_one_or_none()
    
    if not geofence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geofence not found"
        )
    
    is_inside, distance = await geofence_service.check_point_in_geofence(
        geofence, check_data.latitude, check_data.longitude
    )
    
    return GeofenceCheckResponse(
        inside=is_inside,
        geofence_id=geofence.id,
        geofence_name=geofence.name,
        distance_from_center=distance
    )
