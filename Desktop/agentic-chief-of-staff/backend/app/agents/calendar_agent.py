"""Calendar Agent - Manages schedules, appointments, and time-related tasks."""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse


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
- Confirm specific dates and times
- Check for conflicts
- Suggest optimal times based on priorities
- Include timezone awareness
- Consider meeting preparation time

Response Format (JSON):
{
    "action": "schedule|check_availability|update|cancel|optimize|prepare",
    "details": {
        "title": "Meeting title",
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "duration_minutes": 60,
        "attendees": ["person@email.com"],
        "location": "Room/Link",
        "priority": "high|medium|low",
        "notes": "Additional notes"
    },
    "conflicts": [],
    "suggestions": [],
    "response_to_user": "Natural language response"
}"""

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
If this is a scheduling request without specific times, suggest 3 optimal time slots.
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

        # Simulate calendar operations
        action = result.get('action', '')
        if action == 'schedule':
            self._simulate_schedule(result.get('details', {}))

        user_response = result.get('response_to_user', 'Calendar request processed.')

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=user_response,
            thoughts=[f"Action: {action}", f"Details: {json.dumps(result.get('details', {}))}"],
            tool_calls=[{'tool': 'calendar_api', 'action': action, 'params': result.get('details', {})}],
            data=result
        )

    def _create_default_response(self, task: str) -> Dict[str, Any]:
        """Create default response when parsing fails."""
        now = datetime.now()
        suggested_times = [
            (now + timedelta(days=1)).replace(hour=10, minute=0).strftime('%Y-%m-%d %H:%M'),
            (now + timedelta(days=1)).replace(hour=14, minute=0).strftime('%Y-%m-%d %H:%M'),
            (now + timedelta(days=2)).replace(hour=10, minute=0).strftime('%Y-%m-%d %H:%M'),
        ]

        return {
            'action': 'schedule',
            'details': {
                'title': 'New Meeting',
                'notes': task
            },
            'suggestions': suggested_times,
            'response_to_user': f"I'd be happy to help schedule this. Here are some available times: {', '.join(suggested_times)}. Which works best for you?"
        }

    def _simulate_schedule(self, details: Dict[str, Any]):
        """Simulate scheduling an event."""
        event = {
            'id': len(self.calendar_events) + 1,
            'title': details.get('title', 'Untitled'),
            'date': details.get('date'),
            'time': details.get('time'),
            'duration': details.get('duration_minutes', 60),
            'attendees': details.get('attendees', []),
            'created_at': datetime.now().isoformat()
        }
        self.calendar_events.append(event)
        return event
