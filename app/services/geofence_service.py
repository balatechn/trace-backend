"""
Geofencing service for location-based alerts
"""
import math
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Geofence, GeofenceType, Device, Alert, AlertType, AlertSeverity


class GeofenceService:
    """Service for geofence calculations and violation detection"""
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees).
        Returns distance in meters.
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in meters
        r = 6371000
        return c * r
    
    @staticmethod
    def point_in_polygon(lat: float, lon: float, polygon: List[dict]) -> bool:
        """
        Check if a point is inside a polygon using ray casting algorithm.
        polygon is a list of dicts with 'latitude' and 'longitude' keys.
        """
        n = len(polygon)
        inside = False
        
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]['longitude'], polygon[i]['latitude']
            xj, yj = polygon[j]['longitude'], polygon[j]['latitude']
            
            if ((yi > lat) != (yj > lat)) and \
               (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    async def check_point_in_geofence(
        self,
        geofence: Geofence,
        latitude: float,
        longitude: float
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if a point is within a geofence.
        Returns (is_inside, distance_from_boundary)
        """
        if geofence.fence_type == GeofenceType.CIRCLE:
            distance = self.haversine_distance(
                latitude, longitude,
                geofence.center_latitude, geofence.center_longitude
            )
            is_inside = distance <= geofence.radius_meters
            return is_inside, distance
        
        elif geofence.fence_type == GeofenceType.POLYGON:
            if not geofence.polygon_coordinates:
                return False, None
            is_inside = self.point_in_polygon(
                latitude, longitude, geofence.polygon_coordinates
            )
            return is_inside, None
        
        return False, None
    
    async def check_all_geofences(
        self,
        db: AsyncSession,
        device: Device,
        latitude: float,
        longitude: float
    ) -> List[Alert]:
        """
        Check device location against all active geofences.
        Returns list of generated alerts.
        """
        # Get active geofences (all or department-specific)
        query = select(Geofence).where(Geofence.is_active == True)
        if device.department:
            query = query.where(
                (Geofence.department == None) | 
                (Geofence.department == device.department)
            )
        
        result = await db.execute(query)
        geofences = result.scalars().all()
        
        alerts = []
        
        for geofence in geofences:
            is_inside, distance = await self.check_point_in_geofence(
                geofence, latitude, longitude
            )
            
            # Check for exit violation
            if geofence.alert_on_exit and not is_inside:
                # Check if there's already an unresolved alert for this
                existing_alert = await db.execute(
                    select(Alert).where(
                        Alert.device_id == device.id,
                        Alert.geofence_id == geofence.id,
                        Alert.alert_type == AlertType.GEOFENCE_EXIT,
                        Alert.is_resolved == False
                    )
                )
                if not existing_alert.scalar_one_or_none():
                    alert = Alert(
                        device_id=device.id,
                        alert_type=AlertType.GEOFENCE_EXIT,
                        severity=AlertSeverity.HIGH,
                        title=f"Device left geofence: {geofence.name}",
                        message=f"Device {device.asset_id} has left the allowed zone '{geofence.name}'",
                        latitude=latitude,
                        longitude=longitude,
                        geofence_id=geofence.id
                    )
                    db.add(alert)
                    alerts.append(alert)
            
            # Check for enter alert (if configured)
            if geofence.alert_on_enter and is_inside:
                existing_alert = await db.execute(
                    select(Alert).where(
                        Alert.device_id == device.id,
                        Alert.geofence_id == geofence.id,
                        Alert.alert_type == AlertType.GEOFENCE_ENTER,
                        Alert.is_resolved == False
                    )
                )
                if not existing_alert.scalar_one_or_none():
                    alert = Alert(
                        device_id=device.id,
                        alert_type=AlertType.GEOFENCE_ENTER,
                        severity=AlertSeverity.MEDIUM,
                        title=f"Device entered geofence: {geofence.name}",
                        message=f"Device {device.asset_id} has entered zone '{geofence.name}'",
                        latitude=latitude,
                        longitude=longitude,
                        geofence_id=geofence.id
                    )
                    db.add(alert)
                    alerts.append(alert)
        
        if alerts:
            await db.commit()
        
        return alerts


geofence_service = GeofenceService()
