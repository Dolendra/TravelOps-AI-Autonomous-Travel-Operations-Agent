import os
import logging
import urllib.request
import urllib.parse
import json
from typing import Dict, Any

logger = logging.getLogger("travelops.services.weather")

class WeatherService:
    COORDINATES = {
        "bangalore": (12.9716, 77.5946),
        "hyderabad": (17.3850, 78.4867),
        "delhi": (28.6139, 77.2090),
        "jaipur": (26.9124, 75.7873),
        "mumbai": (19.0760, 72.8777),
        "pune": (18.5204, 73.8567)
    }

    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm"
    }

    @classmethod
    def get_weather_forecast(cls, destination: str, travel_date: str = "") -> Dict[str, Any]:
        """Fetches live weather forecast from Open-Meteo public API, falling back to mock forecasts."""
        dest_key = destination.lower().strip()
        coords = cls.COORDINATES.get(dest_key)

        if coords:
            lat, lon = coords
            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                req = urllib.request.Request(url, headers={"User-Agent": "TravelOps-AI-Client"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if "current_weather" in data:
                        cw = data["current_weather"]
                        temp = cw.get("temperature")
                        code = cw.get("weathercode", 0)
                        condition = cls.WEATHER_CODES.get(code, "Partly cloudy")
                        
                        return {
                            "success": True,
                            "temperature": f"{temp}°C",
                            "condition": condition,
                            "source": "Open-Meteo API",
                            "travel_date": travel_date
                        }
            except Exception as e:
                logger.warning(f"Open-Meteo weather API call failed, falling back to calculation: {e}")

        # Fallback if API fails or coordinates are missing
        # Deterministic mock based on city name length or default
        val = len(destination) % 3
        if val == 0:
            temp = "26°C"
            condition = "Partly cloudy"
        elif val == 1:
            temp = "31°C"
            condition = "Clear sky"
        else:
            temp = "24°C"
            condition = "Slight rain"

        return {
            "success": True,
            "temperature": temp,
            "condition": condition,
            "source": "Mock Forecast Database",
            "travel_date": travel_date
        }
