"""
API routes package
"""
from fastapi import APIRouter
from app.api.routes import auth, users, devices, agent, locations, geofences, alerts, audit

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(devices.router)
api_router.include_router(agent.router)
api_router.include_router(locations.router)
api_router.include_router(geofences.router)
api_router.include_router(alerts.router)
api_router.include_router(audit.router)
