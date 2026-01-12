"""Email Agent - Handles email composition, summarization, and communication tasks."""
import json
import uuid
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse
from app.models.database import db_session, Conversation
from app.services.email_sender import send_email, EmailSendError


class EmailAgent(BaseAgent):
    """
    Email Agent - Executive Communication Management.

    Handles:
    - Email composition and drafting
    - Email summarization
    - Response suggestions
    - Follow-up reminders
    - Communication prioritization
    """

    SYSTEM_PROMPT = """You are the Email Communication Agent - an expert at professional executive communication.

Your capabilities:
1. Draft professional emails with appropriate tone
2. Summarize email threads and conversations
3. Suggest responses to incoming emails
4. Identify priority communications
5. Create follow-up schedules
6. Manage email templates

Communication Guidelines:
- Match tone to recipient (formal for executives, friendly for team)
- Be concise but complete
- Include clear action items
- Use appropriate greetings and closings
- Consider cultural and professional norms

Response Format (JSON):
{
    "action": "compose|summarize|respond|prioritize|follow_up",
    "email_content": {
        "to": "recipient@email.com",
        "to_name": "Recipient Name",
        "subject": "Email subject",
        "body": "Email body content",
        "tone": "formal|friendly|urgent"
    },
    "summary": "Email thread summary if applicable",
    "priority": "high|medium|low",
    "suggested_response_time": "timeframe",
    "response_to_user": "Natural language response"
}

If the user asks to send an email, produce a draft and do not send.
The app requires a confirmation step before sending."""

    def __init__(self):
        super().__init__(
            name="email",
            display_name="Email Manager",
            description="Handles email composition, summarization, and communication management",
            capabilities=[
                "email_composition",
                "email_summarization",
                "response_drafting",
                "priority_management",
                "follow_up_tracking",
                "template_management"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

    async def process(self, state: AgentState) -> AgentResponse:
        """Process email-related requests."""
        conversation_id = state.get('conversation_id')
        if not conversation_id:
            return AgentResponse(
                agent_name=self.name,
                status='needs_clarification',
                message='I need a conversation ID to send email. Please try again.',
                clarification_question='Which conversation should I use to send this email?'
            )

        pending = self._get_pending_email(conversation_id)
        task_text = state.get('task', '')
        if pending and self._is_confirmation(task_text):
            return self._send_pending_email(conversation_id, pending)
        if pending and self._is_cancellation(task_text):
            self._clear_pending_email(conversation_id)
            return AgentResponse(
                agent_name=self.name,
                status='success',
                message='Okay, I will not send that email.',
                data={'action': 'cancel_send'}
            )

        context = self._build_context(state)

        # Retrieve relevant email memories
        memories = await self.retrieve_memories(state['task'], limit=3)
        memory_context = ""
        if memories:
            memory_context = "\n\nPrevious Communication Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}

User's Email Request: {state['task']}

Process this request and provide your response in the specified JSON format.
For email composition, create a professional draft.
For summarization, provide key points and action items.
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
            content=f"Email action: {result.get('action', 'unknown')} - {result.get('email_content', {}).get('subject', state['task'][:50])}",
            memory_type='episodic',
            conversation_id=state.get('conversation_id'),
            importance=0.6
        )

        user_response = result.get('response_to_user', 'Email request processed.')

        # Format email nicely for display
        email_content = result.get('email_content', {})
        if email_content.get('body'):
            formatted_email = self._format_email_display(email_content)
            user_response = f"{user_response}\n\n{formatted_email}\n\nReply “send it” to confirm sending."

        if email_content.get('to') and email_content.get('subject') and email_content.get('body'):
            self._set_pending_email(conversation_id, email_content)
        else:
            user_response += "\n\nPlease provide the recipient email and subject."

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=user_response,
            thoughts=[f"Action: {result.get('action', '')}", f"Tone: {email_content.get('tone', 'professional')}"],
            tool_calls=[{'tool': 'email_api', 'action': result.get('action', ''), 'params': email_content}],
            data=result
        )

    def _create_default_response(self, task: str) -> Dict[str, Any]:
        """Create default response when parsing fails."""
        return {
            'action': 'compose',
            'email_content': {
                'to': '',
                'to_name': '',
                'subject': 'Draft Email',
                'body': task,
                'tone': 'professional'
            },
            'response_to_user': "I've prepared a draft based on your request. Would you like me to refine it?"
        }

    def _format_email_display(self, email_content: Dict[str, Any]) -> str:
        """Format email for display."""
        lines = ["---📧 EMAIL DRAFT ---"]
        if email_content.get('to'):
            to_name = email_content.get('to_name')
            to_display = f"{to_name} <{email_content['to']}>" if to_name else email_content['to']
            lines.append(f"**To:** {to_display}")
        if email_content.get('subject'):
            lines.append(f"**Subject:** {email_content['subject']}")
        lines.append("")
        if email_content.get('body'):
            lines.append(email_content['body'])
        lines.append("\n--- END DRAFT ---")
        return "\n".join(lines)

    def _is_confirmation(self, text: str) -> bool:
        lowered = text.lower().strip()
        return lowered in {
            "send",
            "send it",
            "yes",
            "y",
            "confirm",
            "go ahead",
            "please send",
            "send now"
        }

    def _is_cancellation(self, text: str) -> bool:
        lowered = text.lower().strip()
        return lowered in {
            "cancel",
            "no",
            "don't send",
            "do not send",
            "stop"
        }

    def _get_pending_email(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation or not conversation.metadata_:
                return None
            return conversation.metadata_.get('pending_email')
        finally:
            session.close()

    def _set_pending_email(self, conversation_id: str, email_content: Dict[str, Any]) -> None:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation:
                return
            metadata = conversation.metadata_ or {}
            metadata['pending_email'] = {
                'to': email_content.get('to'),
                'to_name': email_content.get('to_name'),
                'subject': email_content.get('subject'),
                'body': email_content.get('body'),
                'tone': email_content.get('tone')
            }
            conversation.metadata_ = metadata
            session.commit()
        finally:
            session.close()

    def _clear_pending_email(self, conversation_id: str) -> None:
        session = db_session()
        try:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()
            if not conversation or not conversation.metadata_:
                return
            metadata = conversation.metadata_
            metadata.pop('pending_email', None)
            conversation.metadata_ = metadata
            session.commit()
        finally:
            session.close()

    def _send_pending_email(self, conversation_id: str, pending: Dict[str, Any]) -> AgentResponse:
        try:
            send_email(
                to_email=pending.get('to', ''),
                to_name=pending.get('to_name'),
                subject=pending.get('subject', 'No subject'),
                body=pending.get('body', '')
            )
        except EmailSendError as exc:
            return AgentResponse(
                agent_name=self.name,
                status='error',
                message=f"I couldn't send the email: {exc}",
                data={'action': 'send', 'error': str(exc)}
            )

        self._clear_pending_email(conversation_id)
        return AgentResponse(
            agent_name=self.name,
            status='success',
            message="Email sent successfully.",
            data={'action': 'send'}
        )
