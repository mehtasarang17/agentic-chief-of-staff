"""PDF Export Agent for downloading chat transcripts."""
from typing import Dict, Any

from app.agents.base import BaseAgent, AgentState, AgentResponse
from app.config import settings


class PdfAgent(BaseAgent):
    """Agent that provides a PDF download link for the current conversation."""

    SYSTEM_PROMPT = """You are a PDF Export Agent.
Your job is to provide a download link for the current conversation transcript.
Do not summarize or modify the conversation content; just return the link.
"""

    def __init__(self):
        super().__init__(
            name="pdf",
            display_name="PDF Export",
            description="Exports the current conversation as a downloadable PDF",
            capabilities=["pdf_export", "transcript_download"],
            system_prompt=self.SYSTEM_PROMPT
        )

    async def process(self, state: AgentState) -> AgentResponse:
        conversation_id = state.get("conversation_id")
        if not conversation_id:
            return AgentResponse(
                agent_name=self.name,
                status="needs_clarification",
                message="I need a conversation ID to export. Please try again.",
                clarification_question="Which conversation would you like to export?"
            )

        base_url = settings.PUBLIC_API_URL.rstrip("/")
        download_url = f"{base_url}/api/conversations/{conversation_id}/export/pdf"

        return AgentResponse(
            agent_name=self.name,
            status="success",
            message=(
                "Your PDF is ready. "
                f"[Download the chat transcript]({download_url})."
            ),
            data={"download_url": download_url}
        )
