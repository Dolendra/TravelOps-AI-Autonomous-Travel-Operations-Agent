import os
import logging
import urllib.request
import urllib.parse
import json
import math
from typing import Dict, Any

logger = logging.getLogger("travelops.services.maps")

class MapsService:
    COORDINATES = {
        "bangalore": (12.9716, 77.5946),
        "hyderabad": (17.3850, 78.4867),
        "delhi": (28.6139, 77.2090),
        "jaipur": (26.9124, 75.7873),
        "mumbai": (19.0760, 72.8777),
        "pune": (18.5204, 73.8567)
    }

    @classmethod
    def get_route_details(cls, origin: str, destination: str) -> Dict[str, Any]:
        """Fetches distance and duration from Google Maps API, falling back to Haversine calculations."""
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if api_key:
            try:
                url = (
                    f"https://maps.googleapis.com/maps/api/distancematrix/json"
                    f"?origins={urllib.parse.quote(origin)}"
                    f"&destinations={urllib.parse.quote(destination)}"
                    f"&key={api_key}"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "TravelOps-AI-Client"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if data.get("status") == "OK":
                        element = data["rows"][0]["elements"][0]
                        if element.get("status") == "OK":
                            distance_text = element["distance"]["text"]
                            duration_text = element["duration"]["text"]
                            return {
                                "success": True,
                                "distance": distance_text,
                                "duration": duration_text,
                                "source": "Google Maps API"
                            }
            except Exception as e:
                logger.warning(f"Google Maps API call failed, falling back to calculation: {e}")

        # Fallback Geolocation/Haversine calculations
        orig_key = origin.lower().strip()
        dest_key = destination.lower().strip()
        
        o_coords = cls.COORDINATES.get(orig_key)
        d_coords = cls.COORDINATES.get(dest_key)
        
        if o_coords and d_coords:
            lat1, lon1 = o_coords
            lat2, lon2 = d_coords
            
            # Haversine formula
            R = 6371.0  # Earth's radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance_km = R * c
            
            # Estimated driving/road distance factor
            driving_distance = distance_km * 1.15
            # Average speed 65 km/h
            duration_hours = driving_distance / 65.0
            
            hours = int(duration_hours)
            minutes = int((duration_hours - hours) * 60)
            
            dist_text = f"{driving_distance:.1f} km"
            dur_text = f"{hours}h {minutes}m"
            return {
                "success": True,
                "distance": dist_text,
                "duration": dur_text,
                "source": "Haversine Geodistance Model"
            }
            
        # Default fallback if cities are unknown
        return {
            "success": True,
            "distance": "580 km",
            "duration": "9h 0m",
            "source": "Default Route Approximation"
        }
