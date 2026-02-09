"""
Create initial super admin user
Run this script once to create the first admin account
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.models.database import async_session_maker, init_db
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy import select, delete


async def create_admin():
    # Initialize DB tables first
    await init_db()
    
    # Create admin user
    async with async_session_maker() as session:
        # Delete existing admin first
        await session.execute(
            delete(User).where(User.email == "admin@yourcompany.com")
        )
        await session.commit()
        
        admin = User(
            email="admin@yourcompany.com",
            hashed_password=get_password_hash("Admin123!"),
            full_name="System Administrator",
            role=UserRole.SUPER_ADMIN,
            department="IT",
            is_active=True,
            is_verified=True,
            consent_given=True
        )
        
        session.add(admin)
        await session.commit()
        print("Admin user created successfully!")
        print("Email: admin@yourcompany.com")
        print("Password: Admin123!")
        print("\n⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")


if __name__ == "__main__":
    asyncio.run(create_admin())
