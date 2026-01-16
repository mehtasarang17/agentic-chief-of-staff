"""Google Calendar service integration."""
from typing import Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings


class CalendarSendError(Exception):
    """Raised when calendar event creation fails."""


def _get_credentials() -> Credentials:
    if not settings.GOOGLE_CALENDAR_CLIENT_ID or not settings.GOOGLE_CALENDAR_CLIENT_SECRET:
        raise CalendarSendError("Google Calendar credentials are not configured.")
    if not settings.GOOGLE_CALENDAR_REFRESH_TOKEN:
        raise CalendarSendError("Google Calendar refresh token is not configured.")

    return Credentials(
        None,
        refresh_token=settings.GOOGLE_CALENDAR_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CALENDAR_CLIENT_ID,
        client_secret=settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )


def _insert_calendar_event(event: Dict[str, Any], send_updates: Optional[str] = None) -> Dict[str, Any]:
    """Insert a calendar event and return the raw API response."""
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    updates = send_updates or ("all" if event.get("attendees") else "none")
    return service.events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID,
        body=event,
        sendUpdates=updates
    ).execute()


def create_calendar_event(event: Dict[str, Any]) -> str:
    """Create a Google Calendar event and return its HTML link."""
    result = _insert_calendar_event(event)
    return result.get("htmlLink", "")


def create_calendar_event_details(event: Dict[str, Any], send_updates: Optional[str] = None) -> Dict[str, str]:
    """Create a Google Calendar event and return its ID and HTML link."""
    result = _insert_calendar_event(event, send_updates=send_updates)
    return {
        "id": result.get("id", ""),
        "htmlLink": result.get("htmlLink", "")
    }


def add_calendar_event_attendees(event_id: str, attendees: list[Dict[str, Any]]) -> None:
    """Add attendees to an existing event and send invitations."""
    if not event_id:
        raise CalendarSendError("Missing event ID for attendee updates.")
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    try:
        service.events().patch(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            eventId=event_id,
            body={"attendees": attendees},
            sendUpdates="all"
        ).execute()
    except Exception as exc:
        raise CalendarSendError(f"Failed to send invites: {exc}") from exc


def has_calendar_conflict(start_iso: str, end_iso: str, timezone: str) -> bool:
    """Check for busy slots between start and end in the configured calendar."""
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    body = {
        "timeMin": start_iso,
        "timeMax": end_iso,
        "timeZone": timezone,
        "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
    }
    try:
        response = service.freebusy().query(body=body).execute()
    except Exception as exc:
        raise CalendarSendError(f"Failed to check calendar availability: {exc}") from exc

    calendars = response.get("calendars", {})
    busy = calendars.get(settings.GOOGLE_CALENDAR_ID, {}).get("busy", [])
    return bool(busy)
