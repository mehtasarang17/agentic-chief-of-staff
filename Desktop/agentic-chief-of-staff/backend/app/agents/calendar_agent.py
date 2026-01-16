"""Calendar Agent - Manages schedules, appointments, and time-related tasks."""
import json
import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from dateutil import parser as date_parser
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse
from app.models.database import db_session, Conversation
from app.services.calendar_service import (
    create_calendar_event_details,
    has_calendar_conflict,
    CalendarSendError,
)
from app.services.email_sender import send_email, EmailSendError
from app.config import settings


class CalendarAgent(BaseAgent):
    """
    Calendar Agent - Executive Schedule Management.

    Handles:
    - Meeting scheduling and management
    - Availability checking
    - Calendar event creation/updates
    - Schedule optimization
    - Meeting preparation
    """

    SYSTEM_PROMPT = """You are the Calendar Management Agent - an expert at managing executive schedules and time.

Your capabilities:
1. Schedule meetings and appointments
2. Check availability and find optimal meeting times
3. Manage recurring events
4. Send meeting invitations and reminders
5. Optimize daily/weekly schedules
6. Prepare meeting agendas and materials

When responding, always:
- Require attendee email(s), date, time, and meeting title
- If a name is provided without an email, ask for the attendee email (name is optional when email is present)
- Ask for explicit confirmation before creating the event
- Do not suggest random time slots
- Include timezone awareness

Response Format (JSON):
{
    "action": "schedule|check_availability|update|cancel|optimize|prepare",
    "details": {
        "title": "Meeting title",
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "duration_minutes": 60,
        "attendee_name": "Full name",
        "attendee_email": "person@email.com",
        "location": "Room/Link",
        "priority": "high|medium|low",
        "notes": "Additional notes"
    },
    "conflicts": [],
    "suggestions": [],
    "response_to_user": "Natural language response"
}

If the user asks to book an event:
- Ask for attendee email(s), title, date, and time if missing.
- If a name is provided without an email, ask for the attendee email.
- Once required fields are present, ask the user to confirm.
- Only create the calendar event after the user confirms."""

    def __init__(self):
        super().__init__(
            name="calendar",
            display_name="Calendar Manager",
            description="Manages schedules, appointments, meetings, and time optimization",
            capabilities=[
                "meeting_scheduling",
                "availability_check",
                "calendar_management",
                "schedule_optimization",
                "meeting_preparation",
                "reminder_setting"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

        # Simulated calendar data (in production, integrate with Google Calendar, Outlook, etc.)
        self.calendar_events = []

    async def process(self, state: AgentState) -> AgentResponse:
        """Process calendar-related requests."""
        conversation_id = state.get('conversation_id')
        if not conversation_id:
            return AgentResponse(
                agent_name=self.name,
                status='needs_clarification',
                message='I need a conversation ID to schedule an event. Please try again.',
                clarification_question='Which conversation should I use to create the event?'
            )

        pending = self._get_pending_event(conversation_id)
        task_text = state.get('task', '')
        email = self._extract_email(task_text)
        schedule_intent = self._is_schedule_request(task_text)
        history_details = self._extract_details_from_history(state.get('messages', []))
        has_history = bool(history_details)

        if pending or schedule_intent or has_history:
            details = pending.copy() if pending else {}
            details = self._merge_missing_details(details, history_details)
            prev_date = details.get("date")
            prev_time = details.get("time")
            prev_duration = int(details.get("duration_minutes") or 60)
            details = self._apply_extracted_fields(details, task_text, overwrite=True)
            if self._time_fields_changed(details, prev_date, prev_time, prev_duration):
                details.pop("availability_checked", None)
                details.pop("confirmation_snapshot", None)
            if email:
                details["attendee_email"] = email
                details["attendee_email_source"] = "user"

            attendees = details.get("attendees", [])
            if details.get("attendee_name") or details.get("attendee_email"):
                attendees = self._merge_attendees(attendees, [{
                    "name": details.get("attendee_name"),
                    "email": details.get("attendee_email"),
                }])
            details["attendees"] = attendees
            if len(attendees) == 1:
                details["attendee_name"] = attendees[0].get("name")
                details["attendee_email"] = attendees[0].get("email")
                if details.get("attendee_email"):
                    details["attendee_email_source"] = "user"

            self._set_pending_event(conversation_id, details)

            missing = self._missing_required_fields(details)

            if self._is_confirmation(task_text):
                if missing:
                    return AgentResponse(
                        agent_name=self.name,
                        status='needs_clarification',
                        message=f"Please provide the {', '.join(missing)}.",
                        clarification_question="What details should I use?"
                    )
                availability = details.get("availability_checked")
                if availability and availability.get("status") == "conflict":
                    return AgentResponse(
                        agent_name=self.name,
                        status='needs_clarification',
                        message="That time conflicts with an existing event. Please choose another date or time.",
                        clarification_question="What date and time should I book instead?"
                    )
                if not availability:
                    try:
                        start_dt, end_dt = self._build_event_times(details)
                        if has_calendar_conflict(
                            start_dt.isoformat(),
                            end_dt.isoformat(),
                            settings.GOOGLE_CALENDAR_TIMEZONE
                        ):
                            details["availability_checked"] = {
                                "date": details.get("date"),
                                "time": details.get("time"),
                                "duration_minutes": int(details.get("duration_minutes") or 60),
                                "status": "conflict",
                                "checked_at": datetime.utcnow().isoformat(),
                            }
                            self._set_pending_event(conversation_id, details)
                            return AgentResponse(
                                agent_name=self.name,
                                status='needs_clarification',
                                message="That time conflicts with an existing event. Please choose another date or time.",
                                clarification_question="What date and time should I book instead?"
                            )
                        details["availability_checked"] = {
                            "date": details.get("date"),
                            "time": details.get("time"),
                            "duration_minutes": int(details.get("duration_minutes") or 60),
                            "status": "clear",
                            "checked_at": datetime.utcnow().isoformat(),
                        }
                        self._set_pending_event(conversation_id, details)
                    except CalendarSendError as exc:
                        return AgentResponse(
                            agent_name=self.name,
                            status='error',
                            message=f"I couldn't check calendar availability: {exc}",
                            data={'action': 'schedule', 'error': str(exc)}
                        )
                    except ValueError:
                        pass
                return self._send_pending_event(conversation_id, details)

            if missing:
                return AgentResponse(
                    agent_name=self.name,
                    status='needs_clarification',
                    message=f"Please provide the {', '.join(missing)}.",
                    clarification_question="What details should I use?"
                )

            try:
                start_dt, end_dt = self._build_event_times(details)
                if self._availability_check_is_fresh(details):
                    return AgentResponse(
                        agent_name=self.name,
                        status='needs_clarification',
                        message=self._build_confirmation_message(details),
                        clarification_question='Confirm booking?'
                    )
                if has_calendar_conflict(start_dt.isoformat(), end_dt.isoformat(), settings.GOOGLE_CALENDAR_TIMEZONE):
                    details["availability_checked"] = {
                        "date": details.get("date"),
                        "time": details.get("time"),
                        "duration_minutes": int(details.get("duration_minutes") or 60),
                        "status": "conflict",
                        "checked_at": datetime.utcnow().isoformat(),
                    }
                    details.pop("confirmation_snapshot", None)
                    self._set_pending_event(conversation_id, details)
                    return AgentResponse(
                        agent_name=self.name,
                        status='needs_clarification',
                        message="That time conflicts with an existing event. Please choose another date or time.",
                        clarification_question="What date and time should I book instead?"
                    )
                details["availability_checked"] = {
                    "date": details.get("date"),
                    "time": details.get("time"),
                    "duration_minutes": int(details.get("duration_minutes") or 60),
                    "status": "clear",
                    "checked_at": datetime.utcnow().isoformat(),
                }
                details["confirmation_snapshot"] = {
                    "date": details.get("date"),
                    "time": details.get("time"),
                    "duration_minutes": int(details.get("duration_minutes") or 60),
                    "status": "clear",
                    "checked_at": datetime.utcnow().isoformat(),
                }
                self._set_pending_event(conversation_id, details)
            except CalendarSendError as exc:
                return AgentResponse(
                    agent_name=self.name,
                    status='error',
                    message=f"I couldn't check calendar availability: {exc}",
                    data={'action': 'schedule', 'error': str(exc)}
                )
            except ValueError:
                pass

            return AgentResponse(
                agent_name=self.name,
                status='needs_clarification',
                message=self._build_confirmation_message(details),
                clarification_question='Confirm booking?'
            )

        context = self._build_context(state)

        # Retrieve relevant calendar memories
        memories = await self.retrieve_memories(state['task'], limit=3, memory_type='episodic')
        memory_context = ""
        if memories:
            memory_context = "\n\nPrevious Calendar Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        # Get current date/time context
        now = datetime.now()
        time_context = f"""
Current Date: {now.strftime('%A, %B %d, %Y')}
Current Time: {now.strftime('%I:%M %p')}
Timezone: Local
"""

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}

Time Context:
{time_context}

User's Calendar Request: {state['task']}

Analyze this request and provide your response in the specified JSON format.
If this is a scheduling request without a specific attendee email, meeting title, date, or time, ask the user for the missing details.
Only ask for attendee names when a name is provided without an email.
""")
        ]

        response_text = await self._call_llm(messages)

        # Parse response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                result = json.loads(response_text[json_start:json_end])
            else:
                result = self._create_default_response(state['task'])
        except json.JSONDecodeError:
            result = self._create_default_response(state['task'])

        # Store interaction in memory
        await self.store_memory(
            content=f"Calendar action: {result.get('action', 'unknown')} - {state['task']}",
            memory_type='episodic',
            conversation_id=state.get('conversation_id'),
            importance=0.6
        )

        action = result.get('action', '')

        user_response = result.get('response_to_user', 'Calendar request processed.')
        needs_clarification = False
        clarification_question = None

        details = result.get('details', {})

        return AgentResponse(
            agent_name=self.name,
            status='needs_clarification' if needs_clarification else 'success',
            message=user_response,
            thoughts=[f"Action: {action}", f"Details: {json.dumps(result.get('details', {}))}"],
            tool_calls=[{'tool': 'calendar_api', 'action': action, 'params': result.get('details', {})}],
            data=result,
            clarification_question=clarification_question
        )

    def _create_default_response(self, task: str) -> Dict[str, Any]:
        """Create default response when parsing fails."""
        return {
            'action': 'schedule',
            'details': {
                'title': 'New Meeting',
                'notes': task
            },
            'suggestions': [],
            'response_to_user': "Please share the meeting title, date, time, and attendee email."
        }

    def _simulate_schedule(self, details: Dict[str, Any]):
        """Simulate scheduling an event."""
        event = {
            'id': len(self.calendar_events) + 1,
            'title': details.get('title', 'Untitled'),
            'date': details.get('date'),
            'time': details.get('time'),
            'duration': details.get('duration_minutes', 60),
            'attendee_name': details.get('attendee_name'),
            'attendee_email': details.get('attendee_email'),
            'created_at': datetime.now().isoformat()
        }
        self.calendar_events.append(event)
        return event

    def _extract_email(self, text: str) -> Optional[str]:
        emails = self._extract_emails(text)
        return emails[0] if emails else None

    def _extract_emails(self, text: str) -> list[str]:
        if not text:
            return []
        return re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

    def _extract_attendee_name(self, text: str) -> Optional[str]:
        if not text:
            return None
        non_name_terms = {
            "am",
            "meeting",
            "sync",
            "kickoff",
            "review",
            "standup",
            "retro",
            "planning",
            "pm",
            "demo",
            "update",
            "check-in",
            "checkin",
            "status",
        }
        labeled_match = re.search(
            r"(?:attendee name|name)\s*[:\-]\s*([^,;\n]+)",
            text,
            flags=re.IGNORECASE
        )
        if labeled_match:
            return labeled_match.group(1).strip()
        phrase_match = re.search(
            r"(?:his name is|her name is|their name is|name is)\s+([^,.;\n]+)",
            text,
            flags=re.IGNORECASE
        )
        if phrase_match:
            return phrase_match.group(1).strip()
        titled_match = re.search(
            r"\b(Mr|Ms|Mrs|Dr|Prof)\.?\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,3})",
            text
        )
        if titled_match:
            return f"{titled_match.group(1)} {titled_match.group(2)}".strip()
        named_match = re.search(
            r"(?:name is|attendee name is|attendee is)\s+([^,.;]+)",
            text,
            flags=re.IGNORECASE
        )
        if named_match:
            return named_match.group(1).strip()
        email = self._extract_email(text)
        if email:
            before_email = text.split(email)[0]
            clause = re.split(r"[.\n,;]", before_email)[-1].strip()
            if clause:
                words = clause.split()
                stopwords = {
                    "invite",
                    "inviting",
                    "schedule",
                    "scheduling",
                    "meeting",
                    "meet",
                    "with",
                    "for",
                    "book",
                    "booking",
                    "set",
                    "setup",
                    "set-up",
                    "call",
                }
                while words and words[0].lower() in stopwords:
                    words = words[1:]
                candidate = " ".join(words[-4:]).strip()
                if (
                    candidate
                    and len(candidate.split()) <= 4
                    and not any(term in candidate.lower() for term in non_name_terms)
                    and re.match(r"^[A-Za-z][A-Za-z'\-\.]*(?:\s+[A-Za-z][A-Za-z'\-\.]*){0,3}$", candidate)
                ):
                    return candidate
        stripped = text.strip()
        if (
            stripped
            and not self._extract_email(stripped)
            and not self._is_confirmation(stripped)
            and not re.search(r"\d", stripped)
        ):
            simple_name_match = re.match(r"^[A-Za-z][A-Za-z'\-\.]*(?:\s+[A-Za-z][A-Za-z'\-\.]*){0,3}$", stripped)
            if simple_name_match and not any(term in stripped.lower() for term in non_name_terms):
                return stripped
        return None

    def _extract_datetime(self, text: str) -> Optional[Dict[str, str]]:
        if not text:
            return None
        lowered = text.lower()
        now = datetime.now()
        month = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        date_patterns = [
            rf"\b{month}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,)?(?:\s+\d{{4}})?\b",
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{month}(?:\s+\d{{4}})?\b",
            r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",
        ]
        time_patterns = [
            r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b",
            r"\b\d{1,2}:\d{2}\b",
        ]
        relative_date = None
        if "day after tomorrow" in lowered:
            relative_date = (now + timedelta(days=2)).date()
        elif "tomorrow" in lowered:
            relative_date = (now + timedelta(days=1)).date()
        elif "today" in lowered:
            relative_date = now.date()
        else:
            weekday_match = re.search(
                r"\b(next\s+)?(mon|monday|tue|tues|tuesday|wed|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\b",
                lowered
            )
            if weekday_match:
                weekday_map = {
                    "mon": 0,
                    "monday": 0,
                    "tue": 1,
                    "tues": 1,
                    "tuesday": 1,
                    "wed": 2,
                    "wednesday": 2,
                    "thu": 3,
                    "thur": 3,
                    "thurs": 3,
                    "thursday": 3,
                    "fri": 4,
                    "friday": 4,
                    "sat": 5,
                    "saturday": 5,
                    "sun": 6,
                    "sunday": 6,
                }
                target_day = weekday_map[weekday_match.group(2)]
                days_ahead = (target_day - now.weekday()) % 7
                if days_ahead == 0 and weekday_match.group(1):
                    days_ahead = 7
                relative_date = (now + timedelta(days=days_ahead)).date()
        date_match = None
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_match = match.group(0)
                break
        time_match = None
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                time_match = match.group(0)
                break
        if not time_match:
            noon_match = re.search(r"\b(noon|midnight)\b", lowered)
            if noon_match:
                time_match = noon_match.group(0)
        if not date_match and not time_match and not relative_date:
            return None
        result = {}
        if date_match:
            try:
                parsed_date = date_parser.parse(date_match, fuzzy=True, default=now)
                result["date"] = parsed_date.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                return None
        elif relative_date:
            result["date"] = relative_date.strftime("%Y-%m-%d")
        if time_match:
            try:
                if time_match.lower() == "noon":
                    result["time"] = "12:00"
                elif time_match.lower() == "midnight":
                    result["time"] = "00:00"
                else:
                    parsed_time = date_parser.parse(time_match, fuzzy=True, default=now)
                    result["time"] = parsed_time.strftime("%H:%M")
            except (ValueError, TypeError):
                return None
        return result

    def _apply_extracted_fields(self, details: Dict[str, Any], text: str, overwrite: bool = False) -> Dict[str, Any]:
        updated = details.copy()
        attendees = updated.get("attendees", [])
        extracted_attendees = self._extract_attendees(text)
        if extracted_attendees:
            attendees = self._merge_attendees(attendees, extracted_attendees)
            updated["attendees"] = attendees

        email = self._extract_email(text)
        if email and (overwrite or not updated.get("attendee_email")):
            updated["attendee_email"] = email
            updated["attendee_email_source"] = "user"
        name = self._extract_attendee_name(text)
        if name and (overwrite or not updated.get("attendee_name")):
            updated["attendee_name"] = name
        parsed = self._extract_datetime(text)
        title_match = re.search(
            r"(?:meeting title|title|subject)\s*[:\-]\s*([^,;\n]+)",
            text,
            flags=re.IGNORECASE
        )
        if title_match and (overwrite or not updated.get("title")):
            updated["title"] = title_match.group(1).strip()
        elif (overwrite or not updated.get("title")) and not updated.get("title"):
            candidate = text.strip()
            if (
                candidate
                and not self._extract_emails(candidate)
                and not parsed
                and not self._is_confirmation(candidate)
                and not self._extract_attendee_name(candidate)
            ):
                updated["title"] = candidate
        if parsed:
            if parsed.get("date") and (overwrite or not updated.get("date")):
                updated["date"] = parsed["date"]
            if parsed.get("time") and (overwrite or not updated.get("time")):
                updated["time"] = parsed["time"]
        if not updated.get("notes"):
            notes_match = re.search(r"(?:about|regarding)\s+(.+)$", text, re.IGNORECASE)
            if notes_match:
                updated["notes"] = notes_match.group(1).strip()
        return updated

    def _is_schedule_request(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(keyword in lowered for keyword in (
            "schedule",
            "book",
            "meeting",
            "appointment",
            "calendar",
            "invite"
        ))

    def _extract_details_from_history(self, messages: list) -> Dict[str, Any]:
        if not messages:
            return {}
        start_idx = None
        for idx in range(len(messages) - 1, -1, -1):
            msg = messages[idx]
            if msg.get('role') == 'user' and self._is_schedule_request(msg.get('content', '')):
                start_idx = idx
                break
        if start_idx is None:
            return {}
        details: Dict[str, Any] = {}
        for msg in messages[start_idx:]:
            if msg.get('role') != 'user':
                continue
            details = self._apply_extracted_fields(details, msg.get('content', ''), overwrite=False)
        return details

    def _merge_missing_details(self, base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = base.copy()
        for key, value in (incoming or {}).items():
            if value is None:
                continue
            if not merged.get(key):
                merged[key] = value
        return merged

    def _is_confirmation(self, text: str) -> bool:
        if not text:
            return False
        return bool(re.search(
            r"\b(confirm|confirmed|yes|yep|yeah|sure|ok|okay|approve|go ahead|sounds good|book it|do it|please do)\b",
            text.strip(),
            flags=re.IGNORECASE
        ))

    def _extract_attendees(self, text: str) -> list[Dict[str, Any]]:
        if not text:
            return []
        attendees: list[Dict[str, Any]] = []
        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        name_pattern = r"[A-Za-z][A-Za-z'\-\.]+(?:\s+[A-Za-z][A-Za-z'\-\.]+){0,3}"
        pair_patterns = [
            rf"({name_pattern})\s*<\s*({email_pattern})\s*>",
            rf"({name_pattern})\s*\(\s*({email_pattern})\s*\)",
            rf"({name_pattern})\s*[:\-]\s*({email_pattern})",
        ]
        for pattern in pair_patterns:
            for name, email in re.findall(pattern, text, flags=re.IGNORECASE):
                cleaned_name = self._normalize_attendee_name(name)
                if cleaned_name:
                    attendees.append({"name": cleaned_name, "email": email.strip()})
                else:
                    attendees.append({"email": email.strip()})

        name_phrase = re.search(
            r"(?:his name is|her name is|their name is|name is)\s+([^,.;\n]+)",
            text,
            flags=re.IGNORECASE
        )
        email_phrase = re.search(
            rf"(?:email(?:id)? is|email(?: address)? is)\s*({email_pattern})",
            text,
            flags=re.IGNORECASE
        )
        if name_phrase or email_phrase:
            attendees.append({
                "name": name_phrase.group(1).strip() if name_phrase else None,
                "email": email_phrase.group(1).strip() if email_phrase else None
            })

        names = self._extract_name_list(text)
        for name in names:
            attendees.append({"name": name})

        emails = self._extract_emails(text)
        for email in emails:
            if not any((att.get("email") or "").lower() == email.lower() for att in attendees):
                attendees.append({"email": email})

        single_name = self._extract_attendee_name(text)
        if single_name and not any((att.get("name") or "").lower() == single_name.lower() for att in attendees):
            attendees.append({"name": single_name})

        return attendees

    def _extract_name_list(self, text: str) -> list[str]:
        if not text:
            return []
        match = re.search(r"(?:with|invite|inviting|attendees?)\s+([^.;]+)", text, flags=re.IGNORECASE)
        if not match:
            return []
        chunk = match.group(1)
        chunk = re.split(r"\b(on|at|for|about|regarding)\b", chunk, maxsplit=1, flags=re.IGNORECASE)[0]
        parts = re.split(r",| and ", chunk)
        names: list[str] = []
        for part in parts:
            candidate = part.strip()
            if not candidate:
                continue
            if re.search(r"\b(friend|parents|team|colleagues)\b", candidate, re.IGNORECASE):
                continue
            if re.match(r"^[A-Z][A-Za-z'\-\.]*(?:\s+[A-Z][A-Za-z'\-\.]*){0,3}$", candidate):
                names.append(candidate)
        return names

    def _merge_attendees(self, existing: list[Dict[str, Any]], new: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        merged = [att.copy() for att in (existing or []) if att.get("name") or att.get("email")]
        for attendee in new or []:
            name = attendee.get("name")
            email = attendee.get("email")
            if not name and not email:
                continue
            if email:
                match = next((att for att in merged if (att.get("email") or "").lower() == email.lower()), None)
                if match:
                    if name and not match.get("name"):
                        match["name"] = name
                    continue
                if not name:
                    name_only = [att for att in merged if att.get("name") and not att.get("email")]
                    if len(name_only) == 1:
                        name_only[0]["email"] = email
                        continue
                if name:
                    name_match = next((att for att in merged if (att.get("name") or "").lower() == name.lower()), None)
                    if name_match:
                        if not name_match.get("email"):
                            name_match["email"] = email
                        continue
                merged.append({"name": name, "email": email})
                continue
            if name:
                match = next((att for att in merged if (att.get("name") or "").lower() == name.lower()), None)
                if match:
                    continue
                email_only = [att for att in merged if att.get("email") and not att.get("name")]
                if len(email_only) == 1:
                    email_only[0]["name"] = name
                    continue
                merged.append({"name": name})
        return merged

    def _missing_required_fields(self, details: Dict[str, Any]) -> list[str]:
        missing: list[str] = []
        if not details.get("title"):
            missing.append("title")
        if not details.get("date"):
            missing.append("date")
        if not details.get("time"):
            missing.append("time")

        attendees = details.get("attendees", [])
        if not attendees:
            missing.append("attendee email")
            return missing

        missing_emails = [att for att in attendees if not att.get("email")]
        if missing_emails:
            label = ", ".join(att.get("name") or "unknown attendee" for att in missing_emails)
            missing.append(f"attendee email for {label}")
        return missing

    def _time_fields_changed(
        self,
        details: Dict[str, Any],
        prev_date: Optional[str],
        prev_time: Optional[str],
        prev_duration: int
    ) -> bool:
        return (
            details.get("date") != prev_date
            or details.get("time") != prev_time
            or int(details.get("duration_minutes") or 60) != prev_duration
        )

    def _availability_check_is_fresh(self, details: Dict[str, Any], ttl_minutes: int = 5) -> bool:
        check = details.get("availability_checked")
        if not check:
            return False
        if check.get("date") != details.get("date"):
            return False
        if check.get("time") != details.get("time"):
            return False
        if int(check.get("duration_minutes") or 60) != int(details.get("duration_minutes") or 60):
            return False
        checked_at = check.get("checked_at")
        if not checked_at:
            return False
        try:
            checked_dt = datetime.fromisoformat(checked_at)
        except ValueError:
            return False
        return datetime.utcnow() - checked_dt <= timedelta(minutes=ttl_minutes)

    def _confirmation_snapshot_is_valid(self, details: Dict[str, Any]) -> bool:
        snapshot = details.get("confirmation_snapshot")
        if not snapshot:
            return False
        if snapshot.get("status") != "clear":
            return False
        if snapshot.get("date") != details.get("date"):
            return False
        if snapshot.get("time") != details.get("time"):
            return False
        if int(snapshot.get("duration_minutes") or 60) != int(details.get("duration_minutes") or 60):
            return False
        return True

    def _normalize_attendee_name(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        tokens = [token for token in name.strip().split() if token]
        if not tokens:
            return None
        if tokens[0].lower() in {"am", "pm"}:
            tokens = tokens[1:]
        cleaned = " ".join(tokens).strip()
        return cleaned or None

    def _format_attendees_for_user(self, attendees: list[Dict[str, Any]]) -> str:
        formatted = []
        for attendee in attendees or []:
            name = (attendee.get("name") or "").strip()
            email = (attendee.get("email") or "").strip()
            if not name and not email:
                continue
            if name and email:
                cleaned = self._normalize_attendee_name(name)
                formatted.append(f"{cleaned or name} <{email}>")
            elif email:
                formatted.append(email)
            else:
                formatted.append(self._normalize_attendee_name(name) or name)
        return ", ".join(formatted) if formatted else "None"

    def _build_confirmation_message(self, details: Dict[str, Any]) -> str:
        title = details.get("title") or "Meeting"
        date = details.get("date") or "TBD"
        time = details.get("time") or "TBD"
        attendees = self._format_attendees_for_user(details.get("attendees", []))
        timezone = settings.GOOGLE_CALENDAR_TIMEZONE
        lines = [
            "Please confirm the meeting details:",
            f"Title: {title}",
            f"When: {date} {time} ({timezone})",
            f"Attendees: {attendees}",
        ]
        if details.get("location"):
            lines.append(f"Location: {details.get('location')}")
        lines.append('Reply "confirm" to book this meeting and send the invite.')
        return "\n".join(lines)

    def _get_pending_event(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation or not conversation.metadata_:
                return None
            return conversation.metadata_.get('pending_event')
        finally:
            session.close()

    def _set_pending_event(self, conversation_id: str, details: Dict[str, Any]) -> None:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation:
                return
            metadata = conversation.metadata_ or {}
            metadata['pending_event'] = details
            conversation.metadata_ = metadata
            session.commit()
        finally:
            session.close()

    def _clear_pending_event(self, conversation_id: str) -> None:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation or not conversation.metadata_:
                return
            metadata = conversation.metadata_
            metadata.pop('pending_event', None)
            conversation.metadata_ = metadata
            session.commit()
        finally:
            session.close()

    def _send_pending_event(self, conversation_id: str, details: Dict[str, Any]) -> AgentResponse:
        try:
            start_dt, end_dt = self._build_event_times(details)
            event = {
                "summary": details.get("title", "Meeting"),
                "description": details.get("notes") or "Scheduled via Chief of Staff",
                "location": details.get("location"),
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": settings.GOOGLE_CALENDAR_TIMEZONE,
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": settings.GOOGLE_CALENDAR_TIMEZONE,
                },
            }
            event["conferenceData"] = {
                "createRequest": {
                    "requestId": uuid.uuid4().hex,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
            attendees = details.get("attendees") or []
            if not attendees:
                attendee_email = details.get("attendee_email")
                attendee_name = details.get("attendee_name")
                if attendee_email:
                    attendees = [{"email": attendee_email, "name": attendee_name}]

            booking_details = create_calendar_event_details(
                event,
                send_updates="none",
                conference_data_version=1,
            )
            link = booking_details.get("htmlLink", "")
            meet_link = booking_details.get("meetLink", "")
            email_failures: list[str] = []
            if attendees:
                title = details.get("title", "Meeting")
                when = f"{details.get('date')} {details.get('time')} ({settings.GOOGLE_CALENDAR_TIMEZONE})"
                attendees_text = self._format_attendees_for_user(attendees)
                lines = [
                    f"Title: {title}",
                    f"When: {when}",
                ]
                if meet_link:
                    lines.append(f"Google Meet: {meet_link}")
                if details.get("location"):
                    lines.append(f"Location: {details.get('location')}")
                if attendees_text and attendees_text != "None":
                    lines.append(f"Attendees: {attendees_text}")
                lines.append("")
                lines.append("This invite was sent by Chief of Staff.")
                body = "\n".join(lines)
                subject = f"Meeting Invite: {title}"
                for attendee in attendees:
                    email = attendee.get("email")
                    if not email:
                        continue
                    try:
                        send_email(email, subject, body, to_name=attendee.get("name"))
                    except EmailSendError as exc:
                        email_failures.append(f"{email} ({exc})")
        except CalendarSendError as exc:
            return AgentResponse(
                agent_name=self.name,
                status='error',
                message=f"I couldn't create the calendar event: {exc}",
                data={'action': 'schedule', 'error': str(exc)}
            )
        except ValueError as exc:
            self._set_pending_event(conversation_id, details)
            return AgentResponse(
                agent_name=self.name,
                status='needs_clarification',
                message=str(exc),
                clarification_question="What date and time should I use?"
            )

        self._clear_pending_event(conversation_id)
        response = "Event created on your Google Calendar."
        if meet_link:
            response += f" Google Meet link: {meet_link}."
        if attendees:
            if email_failures:
                response += f" I couldn't send the invite to: {', '.join(email_failures)}."
            else:
                response += " Invitations sent via email."
        if link:
            response += f" [Open event]({link})."
        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=response,
            data={'action': 'schedule', 'event_link': link}
        )

    def _build_event_times(self, details: Dict[str, Any]) -> tuple[datetime, datetime]:
        date_str = details.get("date")
        time_str = details.get("time")
        if not date_str or not time_str:
            raise ValueError("Missing date or time for the event.")

        try:
            start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError as exc:
            raise ValueError("Please provide date as YYYY-MM-DD and time as HH:MM (24-hour).") from exc

        try:
            tz = ZoneInfo(settings.GOOGLE_CALENDAR_TIMEZONE)
        except Exception as exc:
            raise ValueError("Invalid Google Calendar timezone setting.") from exc

        start = start.replace(tzinfo=tz)
        duration = int(details.get("duration_minutes") or 60)
        end = start + timedelta(minutes=duration)
        return start, end
