"""
Trace - Enterprise Laptop Asset Management System
Main FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from app.core.config import settings
from app.api import api_router
from app.models import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_default_admin():
    """Create default admin user if none exists"""
    from sqlalchemy import select
    from app.models.database import async_session_maker
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash
    
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.role == UserRole.SUPER_ADMIN))
            admin = result.scalar_one_or_none()
            
            if not admin:
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
                logger.info("Default admin user created: admin@yourcompany.com")
            else:
                logger.info("Admin user already exists")
    except Exception as e:
        logger.error(f"Error creating admin: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Trace Asset Management System...")
    await init_db()
    logger.info("Database initialized")
    await create_default_admin()
    yield
    # Shutdown
    logger.info("Shutting down Trace Asset Management System...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Trace - Enterprise Laptop Asset Management System
    
    Secure web application for company laptop asset management and live location tracking.
    
    ### Features
    - Device registration with serial number, asset ID, employee details
    - Real-time location tracking (GPS / Wi-Fi / IP)
    - Device online/offline status monitoring
    - Role-based access control (Super Admin, IT Admin, Viewer)
    - Geofence zones with alerts
    - Remote lock/wipe capabilities
    - Comprehensive audit logging
    - GDPR-compliant privacy controls
    
    ### Security
    - JWT authentication with token refresh
    - Encrypted communication (HTTPS)
    - Role-based access control
    - Audit logging of all actions
    - Employee consent tracking
    """,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred"}
    )


# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else "Disabled in production",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
