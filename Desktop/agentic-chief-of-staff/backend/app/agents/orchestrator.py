"""Master Orchestrator Agent - The Chief of Staff that delegates to specialized agents."""
import json
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse
from app.config import settings


class MasterOrchestrator(BaseAgent):
    """
    Master Orchestrator Agent - The Chief of Staff.

    This agent:
    1. Analyzes user requests
    2. Determines if clarification is needed
    3. Delegates tasks to specialized agents
    4. Synthesizes results from multiple agents
    5. Provides cohesive responses to users
    """

    SYSTEM_PROMPT = """You are the Chief of Staff AI - a highly capable executive assistant that orchestrates a team of specialized AI agents.

Your role is to:
1. UNDERSTAND: Carefully analyze user requests to determine intent and required actions
2. CLARIFY: Ask for clarification if the request is ambiguous or missing critical information
3. DELEGATE: Route tasks to appropriate specialized agents based on their capabilities
4. SYNTHESIZE: Combine results from multiple agents into cohesive, actionable responses
5. COMMUNICATE: Maintain a professional, helpful, and efficient communication style

Available Specialized Agents:
- CALENDAR: Manages schedules, appointments, meetings, and time-related queries
- EMAIL: Handles email composition, summarization, and communication tasks
- RESEARCH: Conducts research, gathers information, and provides analytical insights
- TASK: Manages to-do lists, project tasks, deadlines, and productivity tracking
- ANALYTICS: Provides data analysis, metrics, reports, and business intelligence
- PDF: Exports the current conversation as a downloadable PDF transcript

Decision Guidelines:
- If the request is clear and specific, delegate to the appropriate agent(s)
- If multiple agents are needed, specify the order of execution
- If clarification is needed, ask ONE focused question
- Always explain your reasoning briefly

Response Format (JSON):
{
    "understanding": "Brief summary of what the user wants",
    "needs_clarification": true/false,
    "clarification_question": "Question if clarification needed, null otherwise",
    "delegations": [
        {
            "agent": "AGENT_NAME",
            "task": "Specific task description",
            "priority": 1-5,
            "context": "Any relevant context for the agent"
        }
    ],
    "reasoning": "Brief explanation of your decision"
}"""

    def __init__(self):
        super().__init__(
            name="orchestrator",
            display_name="Chief of Staff",
            description="Master orchestrator that analyzes requests and delegates to specialized agents",
            capabilities=[
                "request_analysis",
                "task_delegation",
                "agent_coordination",
                "result_synthesis",
                "conversation_management"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

        self.agent_registry: Dict[str, Dict[str, Any]] = {
            "calendar": {
                "keywords": ["schedule", "meeting", "appointment", "calendar", "event", "time", "book", "reschedule", "availability", "remind"],
                "description": "Manages schedules and calendar events"
            },
            "email": {
                "keywords": ["email", "mail", "message", "send", "reply", "draft", "inbox", "compose", "forward", "cc"],
                "description": "Handles email communication"
            },
            "research": {
                "keywords": ["research", "find", "search", "look up", "information", "learn", "analyze", "report", "study", "investigate"],
                "description": "Conducts research and gathers information"
            },
            "task": {
                "keywords": ["task", "todo", "to-do", "deadline", "project", "assign", "complete", "priority", "checklist", "milestone"],
                "description": "Manages tasks and to-do lists"
            },
            "analytics": {
                "keywords": ["analytics", "data", "metrics", "chart", "graph", "trend", "kpi", "dashboard", "statistics", "performance"],
                "description": "Provides data analysis and insights"
            },
            "pdf": {
                "keywords": ["pdf", "download", "export", "transcript", "chat history", "conversation history", "save chat"],
                "description": "Exports chat transcript as a PDF"
            }
        }

    async def process(self, state: AgentState) -> AgentResponse:
        """Process user request and determine delegations."""

        # Build context from state
        context = self._build_context(state)

        # Retrieve relevant memories
        memories = await self.retrieve_memories(state['task'], limit=3)
        memory_context = ""
        if memories:
            memory_context = "\n\nRelevant Past Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        # Prepare messages for LLM
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}

User's Current Request: {state['task']}

Analyze this request and provide your delegation plan in the specified JSON format.
""")
        ]

        # Get LLM response
        response_text = await self._call_llm(messages)

        # Parse the response
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                decision = json.loads(response_text[json_start:json_end])
            else:
                decision = self._fallback_analysis(state['task'])
        except json.JSONDecodeError:
            decision = self._fallback_analysis(state['task'])

        # Store this interaction in memory
        await self.store_memory(
            content=f"User request: {state['task']} | Decision: {decision.get('understanding', '')}",
            memory_type='episodic',
            conversation_id=state.get('conversation_id'),
            importance=0.7
        )

        # Build response
        if decision.get('needs_clarification', False):
            return AgentResponse(
                agent_name=self.name,
                status='needs_clarification',
                message=decision.get('clarification_question', 'Could you please provide more details?'),
                thoughts=[decision.get('understanding', ''), decision.get('reasoning', '')],
                clarification_question=decision.get('clarification_question'),
                data={'decision': decision}
            )

        # Determine next agent
        delegations = decision.get('delegations', [])
        next_agent = None
        if delegations:
            # Sort by priority and get first
            delegations.sort(key=lambda x: x.get('priority', 5))
            next_agent = delegations[0].get('agent', '').lower()

        return AgentResponse(
            agent_name=self.name,
            status='delegated' if next_agent else 'success',
            message=decision.get('understanding', 'I understand your request.'),
            thoughts=[decision.get('understanding', ''), decision.get('reasoning', '')],
            data={
                'decision': decision,
                'delegations': delegations
            },
            next_agent=next_agent
        )

    def _fallback_analysis(self, task: str) -> Dict[str, Any]:
        """Fallback analysis using keyword matching."""
        task_lower = task.lower()

        # Find matching agents
        matching_agents = []
        for agent_name, agent_info in self.agent_registry.items():
            for keyword in agent_info['keywords']:
                if keyword in task_lower:
                    matching_agents.append({
                        'agent': agent_name.upper(),
                        'task': task,
                        'priority': 1,
                        'context': 'Keyword match fallback'
                    })
                    break

        if not matching_agents:
            # Default to research agent for general queries
            matching_agents.append({
                'agent': 'RESEARCH',
                'task': task,
                'priority': 1,
                'context': 'Default delegation'
            })

        return {
            'understanding': f"Processing request: {task}",
            'needs_clarification': False,
            'clarification_question': None,
            'delegations': matching_agents,
            'reasoning': 'Keyword-based delegation'
        }

    async def synthesize_results(self, state: AgentState) -> AgentResponse:
        """Synthesize results from all agents into a cohesive response."""

        results = state.get('results', [])

        if not results:
            return AgentResponse(
                agent_name=self.name,
                status='success',
                message="I wasn't able to gather any results for your request.",
                thoughts=['No results from delegated agents']
            )

        # Build synthesis prompt
        results_summary = "\n".join([
            f"- {r.get('agent_name', 'Unknown')}: {r.get('message', '')} | Data: {json.dumps(r.get('data', {}))}"
            for r in results
        ])

        messages = [
            SystemMessage(content="""You are synthesizing results from multiple AI agents into a cohesive, helpful response for the user.

Guidelines:
- Combine information from all agents naturally
- Highlight the most important findings
- Use clear formatting (bullet points, sections) when helpful
- Be concise but comprehensive
- If there were any errors, mention them briefly
- End with any recommended next steps if applicable"""),
            HumanMessage(content=f"""
Original User Request: {state['task']}

Results from Specialized Agents:
{results_summary}

Please synthesize these results into a cohesive response for the user.
""")
        ]

        synthesized_response = await self._call_llm(messages)

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=synthesized_response,
            thoughts=['Synthesized results from all agents'],
            data={'agent_results': results}
        )
