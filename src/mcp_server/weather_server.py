import os
import warnings
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("Weather Server")

def enforce_presence(**kwargs):
    """Validates that all required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace."""
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")

def format_weather(weather: dict):
    """Converts the OpenWeatherMap API response into the standardized weather data structure returned by this MCP server."""
    offset = weather["timezone"]
    utc = timezone.utc
    sunrise = datetime.fromtimestamp(weather["sys"]["sunrise"] + offset, utc).strftime("%H:%M:%S")
    sunset = datetime.fromtimestamp(weather["sys"]["sunset"] + offset, utc).strftime("%H:%M:%S")
    return {
        "location": weather["name"],
        "country": weather["sys"]["country"],
        "main": weather["weather"][0]["main"],
        "description": weather["weather"][0]["description"],
        "temperature": weather["main"]["temp"],
        "feels_like": weather["main"]["feels_like"],
        "humidity": weather["main"]["humidity"],
        "pressure": weather["main"]["pressure"],
        "visibility": weather["visibility"],
        "wind": weather["wind"],
        "clouds": weather["clouds"],
        "sunrise": sunrise,
        "sunset": sunset
    }

@mcp.tool(name="WeatherReport")
def weather_report(location: str):
    """
Retrieves the current weather conditions for a specified location.

Use this tool when the user requests:
- the current weather,
- today's weather,
- the weather forecast for the current moment,
- temperature,
- humidity,
- wind conditions,
- sunrise or sunset time,
- or other current weather information for a location.

Requires a valid city, town, region, or location name.

Returns the current weather conditions, including temperature, feels-like temperature, weather description, humidity, pressure, visibility, wind, cloud coverage, sunrise, and sunset.

Use this tool only when the user's intent is to retrieve current weather information for a location.
    """
    try:
        enforce_presence(location=location)
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "weather": {}
        }

    try:
        api_key = os.getenv("WEATHER_API_KEY")

        geo = requests.get(
            "http://api.openweathermap.org/geo/1.0/direct",
            params={
                "q": location.strip(),
                "limit": 1,
                "appid": api_key
            },
            timeout=10
        ).json()

        if not geo:
            logger.warning(f"No location found: {location}")
            return {
                "status": "error",
                "message": f"No location found for '{location}'.",
                "weather": {}
            }

        weather = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": geo[0]["lat"],
                "lon": geo[0]["lon"],
                "appid": api_key,
                "units": "metric"
            },
            timeout=10
        ).json()

        logger.info("Weather report retrieved successfully.")

        return {
            "status": "success",
            "message": "Weather retrieved successfully.",
            "weather": format_weather(weather)
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "weather": {}
        }

if __name__ == "__main__":
    mcp.run(transport="stdio")