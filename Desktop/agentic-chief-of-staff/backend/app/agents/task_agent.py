"""Task Agent - Manages to-do lists, projects, and productivity tracking."""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, AgentState, AgentResponse


class TaskAgent(BaseAgent):
    """
    Task Agent - Project and Task Management.

    Handles:
    - Task creation and management
    - Project tracking
    - Deadline management
    - Priority setting
    - Progress tracking
    - Delegation recommendations
    """

    SYSTEM_PROMPT = """You are the Task Management Agent - an expert at managing projects, tasks, and productivity.

Your capabilities:
1. Create and organize tasks with priorities
2. Track project progress and milestones
3. Manage deadlines and due dates
4. Break down complex projects into actionable tasks
5. Identify blockers and dependencies
6. Recommend task delegation and resource allocation

Task Management Guidelines:
- Use clear, actionable task descriptions
- Set realistic deadlines
- Identify dependencies between tasks
- Track progress with measurable metrics
- Prioritize using importance and urgency
- Group related tasks into projects

Response Format (JSON):
{
    "action": "create|update|complete|delete|list|analyze",
    "tasks": [
        {
            "id": "unique_id",
            "title": "Task title",
            "description": "Detailed description",
            "priority": "high|medium|low",
            "status": "pending|in_progress|completed|blocked",
            "due_date": "YYYY-MM-DD",
            "estimated_hours": 2,
            "project": "Project name",
            "dependencies": ["task_id"],
            "assignee": "Person name",
            "tags": ["tag1", "tag2"]
        }
    ],
    "project_summary": {
        "name": "Project name",
        "progress_percent": 45,
        "tasks_completed": 5,
        "tasks_remaining": 6,
        "next_milestone": "Milestone description",
        "blockers": ["Blocker 1"]
    },
    "response_to_user": "Natural language response"
}"""

    def __init__(self):
        super().__init__(
            name="task",
            display_name="Task Manager",
            description="Manages tasks, projects, deadlines, and productivity tracking",
            capabilities=[
                "task_creation",
                "project_management",
                "deadline_tracking",
                "priority_management",
                "progress_tracking",
                "delegation_recommendations"
            ],
            system_prompt=self.SYSTEM_PROMPT
        )

        # Simulated task storage (in production, integrate with task management systems)
        self.tasks: Dict[str, Dict] = {}
        self.projects: Dict[str, Dict] = {}

    async def process(self, state: AgentState) -> AgentResponse:
        """Process task-related requests."""

        context = self._build_context(state)

        # Retrieve relevant task memories
        memories = await self.retrieve_memories(state['task'], limit=3)
        memory_context = ""
        if memories:
            memory_context = "\n\nPrevious Task Context:\n" + "\n".join([
                f"- {m['content']}" for m in memories
            ])

        # Current task list context
        task_list_context = self._get_current_tasks_context()

        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=f"""
{context}
{memory_context}

Current Tasks:
{task_list_context}

User's Task Request: {state['task']}

Process this request and provide your response in the specified JSON format.
For new tasks, create actionable items with clear descriptions and priorities.
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

        # Execute task actions
        action = result.get('action', '')
        if action == 'create':
            self._create_tasks(result.get('tasks', []))
        elif action == 'complete':
            self._complete_tasks(result.get('tasks', []))
        elif action == 'update':
            self._update_tasks(result.get('tasks', []))

        # Store interaction in memory
        await self.store_memory(
            content=f"Task action: {action} - {state['task'][:100]}",
            memory_type='episodic',
            conversation_id=state.get('conversation_id'),
            importance=0.7
        )

        user_response = result.get('response_to_user', 'Task request processed.')

        return AgentResponse(
            agent_name=self.name,
            status='success',
            message=user_response,
            thoughts=[
                f"Action: {action}",
                f"Tasks affected: {len(result.get('tasks', []))}",
            ],
            tool_calls=[{'tool': 'task_api', 'action': action, 'count': len(result.get('tasks', []))}],
            data=result
        )

    def _get_current_tasks_context(self) -> str:
        """Get formatted current tasks context."""
        if not self.tasks:
            return "No current tasks."

        lines = []
        for task_id, task in list(self.tasks.items())[:10]:
            status_emoji = {'pending': '⏳', 'in_progress': '🔄', 'completed': '✅', 'blocked': '🚫'}.get(task.get('status', 'pending'), '📋')
            lines.append(f"{status_emoji} [{task.get('priority', 'medium')}] {task.get('title', 'Untitled')} - Due: {task.get('due_date', 'No date')}")

        return "\n".join(lines) if lines else "No current tasks."

    def _create_tasks(self, tasks: List[Dict]):
        """Create new tasks."""
        for task in tasks:
            task_id = task.get('id', f"task_{len(self.tasks) + 1}")
            task['id'] = task_id
            task['created_at'] = datetime.now().isoformat()
            self.tasks[task_id] = task

    def _complete_tasks(self, tasks: List[Dict]):
        """Mark tasks as complete."""
        for task in tasks:
            task_id = task.get('id')
            if task_id and task_id in self.tasks:
                self.tasks[task_id]['status'] = 'completed'
                self.tasks[task_id]['completed_at'] = datetime.now().isoformat()

    def _update_tasks(self, tasks: List[Dict]):
        """Update existing tasks."""
        for task in tasks:
            task_id = task.get('id')
            if task_id and task_id in self.tasks:
                self.tasks[task_id].update(task)

    def _create_default_response(self, task: str) -> Dict[str, Any]:
        """Create default response when parsing fails."""
        return {
            'action': 'create',
            'tasks': [
                {
                    'id': f"task_{len(self.tasks) + 1}",
                    'title': task[:100],
                    'description': task,
                    'priority': 'medium',
                    'status': 'pending',
                    'due_date': (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                }
            ],
            'response_to_user': f"I've created a new task: '{task[:50]}...'. Would you like to add more details or set a specific deadline?"
        }
