"""Research Agent - Conducts research, gathers information, and provides insights."""
import json
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse


class ResearchAgent(BaseAgent):
    """
    Research Agent - Information Gathering and Analysis.

    Handles:
    - Information research and gathering
    - Document analysis and summarization
    - Competitive intelligence
    - Market research
    - Trend analysis
    """

    SYSTEM_PROMPT = """You are the Research Agent - an expert researcher and analyst providing executive-level insights.

Your capabilities:
1. Conduct thorough research on any topic
2. Analyze and synthesize information from multiple sources
3. Provide executive summaries with key insights
4. Identify trends and patterns
5. Compare alternatives and make recommendations
6. Fact-check and verify information

Research Guidelines:
- Prioritize accuracy and relevance
- Cite sources when available
- Distinguish between facts and opinions
- Provide balanced perspectives
- Highlight key findings prominently
- Include actionable recommendations

Response Format (JSON):
{
    "action": "research|analyze|summarize|compare|fact_check",
    "topic": "Research topic",
    "findings": [
        {
            "title": "Finding title",
            "content": "Detailed finding",
            "confidence": "high|medium|low",
            "source": "Source if available"
        }
    ],
    "key_insights": ["Insight 1", "Insight 2"],
    "recommendations": ["Recommendation 1", "Recommendation 2"],
    "further_research_needed": ["Area 1", "Area 2"],
    "response_to_user": "Natural language response with findings"
}"""

    def __init__(self):
        super().__init__(
            name="research",
            display_name="Research Analyst",
            description="Conducts research, gathers information, and provides analytical insights",
            capabilities=[
                "information_research",
                "document_analysis",
                "trend_analysis",
                "competitive_intelligence",
                "market_research",
                "fact_checking"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

    async def process(self, state: AgentState) -> AgentResponse:
        """Process research-related requests."""

        context = self._build_context(state)

        # Retrieve relevant research memories
        memories = await self.retrieve_memories(state['task'], limit=5)
        memory_context = ""
        if memories:
            memory_context = "\n\nPrevious Research Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        # Check for RAG context
        rag_context = ""
        if state.get('task_context', {}).get('rag_results'):
            rag_results = state['task_context']['rag_results']
            rag_context = "\n\nRelevant Document Context:\n" + "\n".join([
                f"- {r.get('content', '')[:500]}..." for r in rag_results[:3]
            ])

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}
{rag_context}

User's Research Request: {state['task']}

Conduct thorough research on this topic and provide your response in the specified JSON format.
Include key insights, findings, and actionable recommendations.
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
                result = self._create_default_response(state['task'], response_text)
        except json.JSONDecodeError:
            result = self._create_default_response(state['task'], response_text)

        # Store important research in memory
        if result.get('key_insights'):
            await self.store_memory(
                content=f"Research on '{result.get('topic', state['task'][:50])}': {'; '.join(result.get('key_insights', [])[:3])}",
                memory_type='semantic',
                conversation_id=state.get('conversation_id'),
                importance=0.8
            )

        user_response = result.get('response_to_user', 'Research completed.')

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=user_response,
            thoughts=[
                f"Topic: {result.get('topic', '')}",
                f"Findings: {len(result.get('findings', []))} items",
                f"Key Insights: {len(result.get('key_insights', []))} insights"
            ],
            tool_calls=[{'tool': 'research_engine', 'action': result.get('action', 'research'), 'topic': result.get('topic', '')}],
            data=result
        )

    def _create_default_response(self, task: str, llm_response: str = "") -> Dict[str, Any]:
        """Create default response when parsing fails."""
        return {
            'action': 'research',
            'topic': task,
            'findings': [
                {
                    'title': 'Research Results',
                    'content': llm_response if llm_response else 'Research in progress',
                    'confidence': 'medium'
                }
            ],
            'key_insights': [],
            'recommendations': [],
            'response_to_user': llm_response if llm_response else f"I'm researching: {task}. Let me gather more information."
        }
