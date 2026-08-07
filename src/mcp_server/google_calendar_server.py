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
    """
Builds and returns an authenticated Google Calendar service client.
Automatically refreshes expired OAuth credentials when a valid refresh token is available.
    """
    credentials = get_google_credentials(token_file=TOKEN_PATH, client_secrets_file=CREDS_PATH, scopes=SCOPES)
    if getattr(credentials, "expired", False) and getattr(credentials, "refresh_token", None):
        credentials.refresh(Request())
    return build_calendar_service(credentials)

def to_google_datetime(dt_string: str, timezone: str = DEFAULT_TIMEZONE):
    """
Converts a user-provided datetime string into an ISO 8601 datetime accepted by the Google Calendar API.
Supports ISO 8601 strings and common datetime formats. Naive datetimes are localized using the specified timezone.
Raises ValueError if the input format is unsupported.
    """
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
    """Converts a raw Google Calendar event into the standardized event structure returned by this MCP server."""
    return {
        "event_id": event.get("id"),
        "summary": event.get("summary"),
        "description": event.get("description", ""),
        "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date")),
        "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date"))
    }

def select_event(events: list[dict], event_name: str):
    """
Selects the best matching event from a list of candidate events.
Prefers an exact, case-insensitive summary match. If no exact match exists, returns the first candidate.
Returns None when no events are available.
    """
    exact = [e for e in events if e.get("summary", "").strip().lower() == event_name.strip().lower()]
    return exact[0] if exact else (events[0] if events else None)

def enforce_presence(**kwargs):
    """ Validates that required tool arguments are present and non-empty. Raises ValueError when a required argument is missing or contains only whitespace. """
    for key, value in kwargs.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValueError(f"'{key}' is required. Ask the user for this information.")

def validate_datetime_range(start_datetime: str, end_datetime: str, timezone: str = DEFAULT_TIMEZONE):
    """ Validates that the supplied start datetime occurs before the end datetime. Raises ValueError if the time range is invalid. """
    start = datetime.fromisoformat(to_google_datetime(start_datetime, timezone))
    end = datetime.fromisoformat(to_google_datetime(end_datetime, timezone))

    if start >= end:
        raise ValueError("'end_datetime' must be later than 'start_datetime'. Ask the user for a valid time range.")

@mcp.tool(name="Get-Calendar-Events")
def get_events(min_datetime: str, max_datetime: str, query: str = "", max_results: int = 20):
    """
Retrieves events from the user's primary Google Calendar within the specified time range.

Use this tool when the user wants to:
- view scheduled events,
- check availability,
- find meetings,
- search calendar entries,
- list upcoming events,
- or retrieve events matching a specific search query.

Returns every matching calendar event within the requested time range.
    """
    try:
        enforce_presence(min_datetime=min_datetime, max_datetime=max_datetime)
        validate_datetime_range(min_datetime, max_datetime)

    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "events": [],
        }  

    try:
        service = get_calendar_service()

        response = service.events().list(
            calendarId="primary",
            timeMin=to_google_datetime(min_datetime),
            timeMax=to_google_datetime(max_datetime),
            q=query.strip() or None,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = response.get("items", [])

        return {
            "status": "success",
            "message": f"Retrieved {len(events)} event(s) successfully.",
            "events": [format_event(event) for event in events],
        }

    except HttpError as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": f"Google Calendar API Error: {str(e)}",
            "events": []
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "events": []
        }

@mcp.tool(name="Create-Calendar-Event")
def create_event(summary: str, start_datetime: str, end_datetime: str, description: str = "", timezone: str = DEFAULT_TIMEZONE):
    """
Creates a new event in the user's primary Google Calendar.

Use this tool when the user requests to:
- create,
- schedule,
- book,
- add,
- or save a calendar event.

Requires the event title, start datetime, and end datetime.
Returns the created calendar event.
    """
    try:
        enforce_presence(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime
        )
        validate_datetime_range(start_datetime, end_datetime)
        
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "events": [],
        }

    try:
        service = get_calendar_service()

        body = {
            "summary": summary.strip(),
            "description": description.strip() if description else "",
            "start": {
                "dateTime": to_google_datetime(start_datetime, timezone),
                "timeZone": timezone
            },
            "end": {
                "dateTime": to_google_datetime(end_datetime, timezone),
                "timeZone": timezone
            },
        }

        event = service.events().insert(
            calendarId="primary",
            body=body
        ).execute()

        return {
            "status": "success",
            "message": f"Event created successfully.",
            "events": [format_event(event)]
        }

    except HttpError as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": f"Google Calendar API Error: {str(e)}",
            "events": []
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "events": []
        }

@mcp.tool(name="Update-Calendar-Event")
def update_event(event_name: str, summary: str | None = None, start_datetime: str | None = None, end_datetime: str | None = None, description: str | None = None, timezone: str = DEFAULT_TIMEZONE):
    """
Updates an existing event in the user's primary Google Calendar.

Use this tool when the user wants to modify an existing event, including:
- changing the title,
- changing the description,
- rescheduling,
- changing the start or end time,
- or editing event details.

The event is identified by its name. If no matching event is found, the tool returns nearby upcoming events as suggestions.
    """

    try:
        enforce_presence(event_name=event_name)

        if summary is not None:
            enforce_presence(summary=summary)

        if start_datetime is not None and end_datetime is not None:
            validate_datetime_range(start_datetime, end_datetime)

    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "events": [],
        }

    try:
        service = get_calendar_service()

        search_result = service.events().list(
            calendarId="primary",
            q=event_name.strip(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=3
        ).execute()

        events = search_result.get("items", [])
        target_event = select_event(events, event_name)

        if target_event:

            if summary is not None:
                target_event["summary"] = summary.strip()

            if description is not None:
                target_event["description"] = description.strip()

            if start_datetime is not None:
                target_event["start"] = {
                    "dateTime": to_google_datetime(start_datetime, timezone),
                    "timeZone": timezone
                }

            if end_datetime is not None:
                target_event["end"] = {
                    "dateTime": to_google_datetime(end_datetime, timezone),
                    "timeZone": timezone
                }

            updated = service.events().update(
                calendarId="primary",
                eventId=target_event["id"],
                body=target_event
            ).execute()

            return {
                "status": "success",
                "message": f"Event updated successfully.",
                "events": [format_event(updated)]
            }

        now = datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z")

        fallback_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        return {
            "status": "suggestions",
            "message": f"No event named '{event_name}' was found. Here are upcoming events.",
            "events": [format_event(e) for e in fallback_result.get("items", [])]
        }

    except HttpError as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": f"Google Calendar API Error: {str(e)}",
            "events": []
        }

    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": str(e),
            "events": []
        }

@mcp.tool(name="Delete-Calendar-Event")
def delete_event(event_name: str):
    """
Deletes an existing event from the user's primary Google Calendar.

Use this tool when the user requests to:
- delete,
- remove,
- cancel,
- or erase a calendar event.

The event is identified by its name. If no matching event is found, the tool returns nearby upcoming events as suggestions.
    """
    try:
        enforce_presence(event_name=event_name)
    except ValueError as e:
        logger.warning(str(e))
        return {
            "status": "error",
            "message": str(e),
            "events": [],
        }

    try:
        service = get_calendar_service()

        search_result = service.events().list(
            calendarId="primary",
            q=event_name.strip(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=3
        ).execute()

        events = search_result.get("items", [])
        target_event=select_event(events,event_name)

        if target_event:

            service.events().delete(
                calendarId="primary",
                eventId=target_event["id"]
            ).execute()

            return {
                "status": "success",
                "message": f"Event deleted successfully.",
                "events": [format_event(target_event)]
            }

        now = datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z")

        fallback_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        return {
            "status": "suggestions",
            "message": f"No event named '{event_name}' was found to delete. Here are upcoming events.",
            "events": [format_event(e) for e in fallback_result.get("items", [])]
        }

    except HttpError as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": f"Google Calendar API Error: {str(e)}",
            "events": [],
        }
    except Exception as e:
        logger.exception(e)
        return {
            "status": "error",
            "message": f"API Error: {str(e)}", 
            "events": []
        }

if __name__ == "__main__":
    mcp.run()
