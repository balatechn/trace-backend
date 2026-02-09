"""
User management routes
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import get_db, User, UserRole, AuditAction
from app.schemas import (
    UserCreateByAdmin, UserUpdate, UserPasswordChange,
    UserResponse, UserListResponse
)
from app.core.security import (
    get_password_hash, verify_password, get_current_user,
    require_admin, require_super_admin
)
from app.services import audit_service

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    department: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List all users with filtering and pagination.
    Requires IT Admin or Super Admin role.
    """
    query = select(User)
    count_query = select(func.count(User.id))
    
    # Apply filters
    if department:
        query = query.where(User.department == department)
        count_query = count_query.where(User.department == department)
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_filter)) |
            (User.full_name.ilike(search_filter))
        )
        count_query = count_query.where(
            (User.email.ilike(search_filter)) |
            (User.full_name.ilike(search_filter))
        )
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific user by ID.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreateByAdmin,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user (Admin only).
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        department=user_data.department,
        role=user_data.role,
        is_active=user_data.is_active,
        is_verified=user_data.is_verified
    )
    
    db.add(user)
    await db.flush()
    
    await audit_service.log(
        db=db,
        action=AuditAction.USER_CREATE,
        user=current_user,
        request=request,
        target_type="user",
        target_id=user.id,
        target_identifier=user.email,
        description=f"Created user {user.email} with role {user.role.value}"
    )
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user's information.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only super admin can change roles
    if user_data.role and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can change user roles"
        )
    
    # Track changes for audit
    changes = {}
    update_data = user_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if getattr(user, field) != value:
            changes[field] = {"old": str(getattr(user, field)), "new": str(value)}
            setattr(user, field, value)
    
    if changes:
        action = AuditAction.USER_ROLE_CHANGE if "role" in changes else AuditAction.USER_UPDATE
        await audit_service.log(
            db=db,
            action=action,
            user=current_user,
            request=request,
            target_type="user",
            target_id=user.id,
            target_identifier=user.email,
            description=f"Updated user {user.email}",
            details=changes
        )
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user (Super Admin only).
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await audit_service.log(
        db=db,
        action=AuditAction.USER_DELETE,
        user=current_user,
        request=request,
        target_type="user",
        target_id=user.id,
        target_identifier=user.email,
        description=f"Deleted user {user.email}"
    )
    
    await db.delete(user)
    await db.commit()


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a user account.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    user.is_verified = True
    
    await audit_service.log(
        db=db,
        action=AuditAction.USER_UPDATE,
        user=current_user,
        request=request,
        target_type="user",
        target_id=user.id,
        target_identifier=user.email,
        description=f"Activated user {user.email}"
    )
    
    await db.commit()
    
    return {"message": f"User {user.email} activated successfully"}


@router.post("/me/change-password")
async def change_password(
    password_data: UserPasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password.
    """
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    
    await audit_service.log(
        db=db,
        action=AuditAction.PASSWORD_CHANGE,
        user=current_user,
        request=request,
        target_type="user",
        target_id=current_user.id,
        description="Password changed"
    )
    
    await db.commit()
    
    return {"message": "Password changed successfully"}
