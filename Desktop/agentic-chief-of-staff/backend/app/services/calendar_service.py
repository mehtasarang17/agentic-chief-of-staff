"""Google Calendar service integration."""
from typing import Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from dateutil import parser as date_parser
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


def _insert_calendar_event(
    event: Dict[str, Any],
    send_updates: Optional[str] = None,
    conference_data_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Insert a calendar event and return the raw API response."""
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    updates = send_updates or ("all" if event.get("attendees") else "none")
    params = {
        "calendarId": settings.GOOGLE_CALENDAR_ID,
        "body": event,
        "sendUpdates": updates,
    }
    if conference_data_version is not None:
        params["conferenceDataVersion"] = conference_data_version
    return service.events().insert(
        **params
    ).execute()


def _extract_meet_link(result: Dict[str, Any]) -> str:
    link = result.get("hangoutLink")
    if link:
        return link
    conference = result.get("conferenceData", {}) if isinstance(result, dict) else {}
    entry_points = conference.get("entryPoints", []) if isinstance(conference, dict) else []
    for entry in entry_points or []:
        if entry.get("entryPointType") == "video" and entry.get("uri"):
            return entry.get("uri")
    return ""


def create_calendar_event(event: Dict[str, Any]) -> str:
    """Create a Google Calendar event and return its HTML link."""
    result = _insert_calendar_event(event)
    return result.get("htmlLink", "")


def create_calendar_event_details(
    event: Dict[str, Any],
    send_updates: Optional[str] = None,
    conference_data_version: Optional[int] = None,
) -> Dict[str, str]:
    """Create a Google Calendar event and return its ID and HTML link."""
    result = _insert_calendar_event(
        event,
        send_updates=send_updates,
        conference_data_version=conference_data_version,
    )
    return {
        "id": result.get("id", ""),
        "htmlLink": result.get("htmlLink", ""),
        "meetLink": _extract_meet_link(result),
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
    try:
        start_dt = date_parser.isoparse(start_iso)
        end_dt = date_parser.isoparse(end_iso)
    except (ValueError, TypeError) as exc:
        raise CalendarSendError(f"Invalid time range: {exc}") from exc
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
    if not busy:
        return False

    # Fallback to event list to avoid false positives from freebusy.
    try:
        events_result = service.events().list(
            calendarId=settings.GOOGLE_CALENDAR_ID,
            timeMin=start_iso,
            timeMax=end_iso,
            timeZone=timezone,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as exc:
        raise CalendarSendError(f"Failed to confirm calendar conflicts: {exc}") from exc

    events = events_result.get("items", []) if events_result else []
    if not events:
        return False

    try:
        tz = ZoneInfo(timezone)
    except Exception as exc:
        raise CalendarSendError(f"Invalid timezone for conflict check: {exc}") from exc

    for event in events:
        if event.get("status") == "cancelled":
            continue
        if event.get("transparency") == "transparent":
            continue
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        if "dateTime" in start_info and "dateTime" in end_info:
            try:
                event_start = date_parser.isoparse(start_info["dateTime"])
                event_end = date_parser.isoparse(end_info["dateTime"])
            except (ValueError, TypeError):
                continue
        elif "date" in start_info and "date" in end_info:
            try:
                event_start = datetime.fromisoformat(start_info["date"]).replace(tzinfo=tz)
                event_end = datetime.fromisoformat(end_info["date"]).replace(tzinfo=tz)
            except (ValueError, TypeError):
                continue
        else:
            continue
        if event_start < end_dt and event_end > start_dt:
            return True

    return False
