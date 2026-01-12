"""LangGraph workflow for multi-agent orchestration."""
import asyncio
from typing import Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, END

from app.agents.base import AgentState, AgentResponse
from app.agents.orchestrator import MasterOrchestrator
from app.agents.calendar_agent import CalendarAgent
from app.agents.email_agent import EmailAgent
from app.agents.research_agent import ResearchAgent
from app.agents.task_agent import TaskAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.pdf_agent import PdfAgent
from app.config import settings


# Initialize all agents
orchestrator = MasterOrchestrator()
calendar_agent = CalendarAgent()
email_agent = EmailAgent()
research_agent = ResearchAgent()
task_agent = TaskAgent()
analytics_agent = AnalyticsAgent()
pdf_agent = PdfAgent()

# Agent registry
AGENTS = {
    'orchestrator': orchestrator,
    'calendar': calendar_agent,
    'email': email_agent,
    'research': research_agent,
    'task': task_agent,
    'analytics': analytics_agent,
    'pdf': pdf_agent
}


async def orchestrator_node(state: AgentState) -> AgentState:
    """Orchestrator node - analyzes request and delegates."""
    response = await orchestrator.process(state)

    # Update state with response
    new_message = {
        'role': 'assistant',
        'content': response.message,
        'agent_name': response.agent_name,
        'thoughts': response.thoughts,
        'tool_calls': response.tool_calls
    }

    new_results = state.get('results', []).copy()
    new_results.append({
        'agent_name': response.agent_name,
        'status': response.status,
        'message': response.message,
        'data': response.data,
        'summary': response.message[:200]
    })

    return {
        **state,
        'messages': state['messages'] + [new_message],
        'current_agent': 'orchestrator',
        'results': new_results,
        'next_agent': response.next_agent,
        'should_continue': response.status == 'delegated',
        'user_clarification_needed': response.status == 'needs_clarification',
        'clarification_question': response.clarification_question,
        'iteration_count': state.get('iteration_count', 0) + 1
    }


async def calendar_node(state: AgentState) -> AgentState:
    """Calendar agent node."""
    response = await calendar_agent.process(state)
    return _update_state_with_response(state, response, 'calendar')


async def email_node(state: AgentState) -> AgentState:
    """Email agent node."""
    response = await email_agent.process(state)
    return _update_state_with_response(state, response, 'email')


async def research_node(state: AgentState) -> AgentState:
    """Research agent node."""
    response = await research_agent.process(state)
    return _update_state_with_response(state, response, 'research')


async def task_node(state: AgentState) -> AgentState:
    """Task agent node."""
    response = await task_agent.process(state)
    return _update_state_with_response(state, response, 'task')


async def analytics_node(state: AgentState) -> AgentState:
    """Analytics agent node."""
    response = await analytics_agent.process(state)
    return _update_state_with_response(state, response, 'analytics')


async def pdf_node(state: AgentState) -> AgentState:
    """PDF export agent node."""
    response = await pdf_agent.process(state)
    return _update_state_with_response(state, response, 'pdf')


async def synthesizer_node(state: AgentState) -> AgentState:
    """Synthesizer node - combines results from all agents."""
    response = await orchestrator.synthesize_results(state)

    new_message = {
        'role': 'assistant',
        'content': response.message,
        'agent_name': 'synthesizer',
        'thoughts': response.thoughts,
        'is_final': True
    }

    return {
        **state,
        'messages': state['messages'] + [new_message],
        'current_agent': 'synthesizer',
        'should_continue': False,
        'iteration_count': state.get('iteration_count', 0) + 1
    }


def _update_state_with_response(state: AgentState, response: AgentResponse, agent_name: str) -> AgentState:
    """Helper to update state with agent response."""
    new_message = {
        'role': 'assistant',
        'content': response.message,
        'agent_name': response.agent_name,
        'thoughts': response.thoughts,
        'tool_calls': response.tool_calls
    }

    new_results = state.get('results', []).copy()
    new_results.append({
        'agent_name': response.agent_name,
        'status': response.status,
        'message': response.message,
        'data': response.data,
        'summary': response.message[:200]
    })

    return {
        **state,
        'messages': state['messages'] + [new_message],
        'current_agent': agent_name,
        'results': new_results,
        'next_agent': response.next_agent,
        'should_continue': response.next_agent is not None,
        'iteration_count': state.get('iteration_count', 0) + 1
    }


def route_after_orchestrator(state: AgentState) -> str:
    """Determine next step after orchestrator."""
    # Check iteration limit
    if state.get('iteration_count', 0) >= settings.MAX_AGENT_ITERATIONS:
        return 'synthesizer'

    # If clarification needed, go to end (wait for user input)
    if state.get('user_clarification_needed'):
        return END

    # Route to next agent
    next_agent = state.get('next_agent')
    if next_agent and next_agent in AGENTS:
        return 'task_agent' if next_agent == 'task' else next_agent

    # If no delegation, synthesize results
    return 'synthesizer'


def route_after_worker(state: AgentState) -> str:
    """Determine next step after a worker agent."""
    # Check iteration limit
    if state.get('iteration_count', 0) >= settings.MAX_AGENT_ITERATIONS:
        return 'synthesizer'

    # PDF export should end the workflow immediately
    if state.get('current_agent') == 'pdf':
        return END

    # Check if there are more delegations
    delegations = state.get('task_context', {}).get('remaining_delegations', [])
    if delegations:
        next_agent = delegations[0].get('agent', '').lower()
        if next_agent in AGENTS:
            return 'task_agent' if next_agent == 'task' else next_agent

    # Go to synthesizer
    return 'synthesizer'


def create_agent_graph() -> StateGraph:
    """Create the LangGraph workflow for multi-agent orchestration."""

    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node('orchestrator', orchestrator_node)
    workflow.add_node('calendar', calendar_node)
    workflow.add_node('email', email_node)
    workflow.add_node('research', research_node)
    workflow.add_node('task_agent', task_node)
    workflow.add_node('analytics', analytics_node)
    workflow.add_node('pdf', pdf_node)
    workflow.add_node('synthesizer', synthesizer_node)

    # Set entry point
    workflow.set_entry_point('orchestrator')

    # Add conditional edges from orchestrator
    workflow.add_conditional_edges(
        'orchestrator',
        route_after_orchestrator,
        {
            'calendar': 'calendar',
            'email': 'email',
            'research': 'research',
            'task': 'task_agent',
            'analytics': 'analytics',
            'pdf': 'pdf',
            'synthesizer': 'synthesizer',
            END: END
        }
    )

    # Add conditional edges from worker agents
    for agent in ['calendar', 'email', 'research', 'task_agent', 'analytics', 'pdf']:
        workflow.add_conditional_edges(
            agent,
            route_after_worker,
            {
                'calendar': 'calendar',
                'email': 'email',
                'research': 'research',
                'task': 'task_agent',
                'analytics': 'analytics',
                'pdf': 'pdf',
                'synthesizer': 'synthesizer',
                END: END
            }
        )

    # Synthesizer always ends
    workflow.add_edge('synthesizer', END)

    return workflow.compile()


# Create compiled graph
agent_graph = create_agent_graph()


async def run_agent_workflow(
    task: str,
    conversation_id: str,
    messages: list = None,
    context: dict = None
) -> Dict[str, Any]:
    """
    Run the agent workflow for a given task.

    Args:
        task: The user's request/task
        conversation_id: ID of the conversation
        messages: Previous messages in the conversation
        context: Additional context (RAG results, etc.)

    Returns:
        Dict with the final response and agent results
    """
    # Initialize state
    initial_state: AgentState = {
        'messages': messages or [],
        'current_agent': '',
        'task': task,
        'task_context': context or {},
        'results': [],
        'next_agent': None,
        'should_continue': True,
        'user_clarification_needed': False,
        'clarification_question': None,
        'conversation_id': conversation_id,
        'iteration_count': 0
    }

    # Run the graph
    final_state = await agent_graph.ainvoke(initial_state)

    # Extract final response
    final_messages = final_state.get('messages', [])
    final_message = final_messages[-1] if final_messages else {'content': 'No response generated.'}

    return {
        'response': final_message.get('content', ''),
        'agent_name': final_message.get('agent_name', 'unknown'),
        'thoughts': final_message.get('thoughts', []),
        'tool_calls': final_message.get('tool_calls', []),
        'is_final': final_message.get('is_final', False),
        'needs_clarification': final_state.get('user_clarification_needed', False),
        'clarification_question': final_state.get('clarification_question'),
        'all_results': final_state.get('results', []),
        'iteration_count': final_state.get('iteration_count', 0)
    }
