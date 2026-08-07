import logging
import os
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from langchain_google_community.calendar.utils import get_google_credentials, build_calendar_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_DIR = os.path.join(BASE_DIR, "auth")
TOKEN_PATH = os.path.join(AUTH_DIR, "token.json")
CREDS_PATH = os.path.join(AUTH_DIR, "credentials.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TIMEZONE = "Asia/Kolkata"

mcp = FastMCP("Google Calendar Server")

def get_calendar_service():
    credentials = get_google_credentials(token_file=TOKEN_PATH, client_secrets_file=CREDS_PATH, scopes=SCOPES)
    if getattr(credentials, "expired", False) and getattr(credentials, "refresh_token", None):
        credentials.refresh(Request())
    return build_calendar_service(credentials)

def to_google_datetime(dt_string: str, timezone: str = DEFAULT_TIMEZONE):
    try:
        dt = datetime.fromisoformat(dt_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone))
        return dt.isoformat()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(dt_string, fmt)
            dt = dt.replace(tzinfo=ZoneInfo(timezone))
            return dt.isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported datetime format: {dt_string}")

def format_event(event: dict):
    return {
        "event_id": event.get("id"),
        "summary": event.get("summary"),
        "description": event.get("description", ""),
        "start": event["start"].get("dateTime", event["start"].get("date")),
        "end": event["end"].get("dateTime", event["end"].get("date"))
    }

@mcp.tool(name="GetCalendarEvents")
def get_events(min_datetime: str, max_datetime: str, query: str = "", max_results: int = 20):
    """Retrieve calendar events within a specified time range, optionally filtered by a search query."""
    try:
        service = get_calendar_service()
        response = service.events().list(
            calendarId="primary",
            timeMin=to_google_datetime(min_datetime),
            timeMax=to_google_datetime(max_datetime),
            q=query or None,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = response.get("items", [])
        return {
            "status": "success",
            "count": len(events),
            "events": [format_event(event) for event in events],
        }
    except Exception as e:
        logger.exception(e)
        return {"status": "error", "message": str(e), "events": []}

@mcp.tool(name="CreateCalendarEvent")
def create_event(summary: str, start_datetime: str, end_datetime: str, description: str = "", timezone: str = DEFAULT_TIMEZONE):
    """Create a new event in the user's primary Google Calendar."""
    try:
        service = get_calendar_service()
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": to_google_datetime(start_datetime, timezone), "timeZone": timezone},
            "end": {"dateTime": to_google_datetime(end_datetime, timezone), "timeZone": timezone},
        }
        event = service.events().insert(calendarId="primary", body=body).execute()
        return {
            "status": "success",
            "message": "Event created successfully.",
            "events": [format_event(event)]
        }
    except Exception as e:
        logger.exception(e)
        return {"status": "error", "message": str(e), "events": []}

@mcp.tool(name="UpdateCalendarEvent")
def update_event(event_name: str, summary: str | None = None, start_datetime: str | None = None, end_datetime: str | None = None, description: str | None = None, timezone: str = DEFAULT_TIMEZONE):
    """Update an existing event from the user's primary Google Calendar by searching its name."""
    try:
        service = get_calendar_service()

        # Step 1: Search for the exact event by name
        search_result = service.events().list(
            calendarId="primary",
            q=event_name,
            singleEvents=True,
            orderBy="startTime",
            maxResults=1
        ).execute()

        events = search_result.get("items", [])

        # Step 2: If found, apply updates
        if events:
            target_event = events[0]

            if summary is not None:
                target_event["summary"] = summary
            if description is not None:
                target_event["description"] = description
            if start_datetime is not None:
                target_event["start"] = {"dateTime": to_google_datetime(start_datetime, timezone), "timeZone": timezone}
            if end_datetime is not None:
                target_event["end"] = {"dateTime": to_google_datetime(end_datetime, timezone), "timeZone": timezone}

            updated = service.events().update(
                calendarId="primary", 
                eventId=target_event["id"], 
                body=target_event
            ).execute()

            return {
                "status": "success",
                "message": f"Event '{event_name}' updated successfully.",
                "events": [format_event(updated)]
            }

        # Step 3: If not found, fallback to 5 upcoming suggestions
        now = datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z")
        fallback_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        fallback_events = fallback_result.get("items", [])

        return {
            "status": "suggestions",
            "message": f"No event named '{event_name}' was found. Here are upcoming events.",
            "events": [format_event(e) for e in fallback_events]
        }

    except Exception as e:
        logger.exception(e)
        return {"status": "error", "message": str(e), "events": []}

@mcp.tool(name="DeleteCalendarEvent")
def delete_event(event_name: str, timezone: str = DEFAULT_TIMEZONE):
    """Delete an existing event from the user's primary Google Calendar by searching its name."""
    try:
        service = get_calendar_service()

        # Step 1: Search for the exact event by name
        search_result = service.events().list(
            calendarId="primary",
            q=event_name,
            singleEvents=True,
            orderBy="startTime",
            maxResults=1
        ).execute()

        events = search_result.get("items", [])

        # Step 2: If found, delete it immediately
        if events:
            target_event = events[0]
            service.events().delete(calendarId="primary", eventId=target_event["id"]).execute()
            
            return {
                "status": "success",
                "message": f"Event '{event_name}' deleted successfully.",
                "events": [format_event(target_event)]
            }

        # Step 3: If not found, fallback to 5 upcoming suggestions
        now = datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z")
        fallback_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        fallback_events = fallback_result.get("items", [])

        return {
            "status": "suggestions",
            "message": f"No event named '{event_name}' was found. Here are upcoming events.",
            "events": [format_event(e) for e in fallback_events]
        }

    except Exception as e:
        logger.exception(e)
        return {"status": "error", "message": str(e), "events": []}

if __name__ == "__main__":
    mcp.run(transport="stdio")