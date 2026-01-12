"""Base agent class with memory management using LangChain."""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import db_session, Agent, AgentMemory


class AgentState(TypedDict):
    """State passed between agents in the graph."""
    messages: List[Dict[str, Any]]
    current_agent: str
    task: str
    task_context: Dict[str, Any]
    results: List[Dict[str, Any]]
    next_agent: Optional[str]
    should_continue: bool
    user_clarification_needed: bool
    clarification_question: Optional[str]
    conversation_id: str
    iteration_count: int


@dataclass
class AgentResponse:
    """Standardized response from an agent."""
    agent_name: str
    status: str  # success, needs_clarification, delegated, error
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    thoughts: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    next_agent: Optional[str] = None
    clarification_question: Optional[str] = None


class BaseAgent(ABC):
    """Base class for all agents with LangChain memory integration."""

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        capabilities: List[str],
        system_prompt: str
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.capabilities = capabilities
        self.system_prompt = system_prompt
        self.agent_id: Optional[uuid.UUID] = None

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY
        )

        # Initialize embeddings for memory
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY
        )

        # Short-term conversation memory (last 10 exchanges)
        self.short_term_memory = ConversationBufferWindowMemory(
            k=10,
            return_messages=True,
            memory_key="chat_history"
        )

        # Register agent in database
        self._register_agent()

    def _register_agent(self):
        """Register or update agent in database."""
        try:
            session = db_session()
            agent = session.query(Agent).filter_by(name=self.name).first()

            if not agent:
                agent = Agent(
                    name=self.name,
                    display_name=self.display_name,
                    description=self.description,
                    agent_type='worker' if self.name != 'orchestrator' else 'master',
                    capabilities=self.capabilities,
                    system_prompt=self.system_prompt,
                    is_active=True
                )
                session.add(agent)
                session.commit()

            self.agent_id = agent.id
            session.close()
        except Exception as e:
            print(f"Warning: Could not register agent {self.name}: {e}")

    async def store_memory(
        self,
        content: str,
        memory_type: str = 'episodic',
        conversation_id: Optional[str] = None,
        importance: float = 0.5,
        metadata: Dict[str, Any] = None
    ):
        """Store a memory with vector embedding for future retrieval."""
        try:
            # Generate embedding
            embedding = self.embeddings.embed_query(content)

            session = db_session()
            memory = AgentMemory(
                agent_id=self.agent_id,
                conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
                memory_type=memory_type,
                content=content,
                importance=importance,
                embedding=embedding,
                metadata_=metadata or {}
            )
            session.add(memory)
            session.commit()
            session.close()
        except Exception as e:
            print(f"Error storing memory for {self.name}: {e}")

    async def retrieve_memories(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories using vector similarity search."""
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)

            session = db_session()

            # Use pgvector for similarity search
            from sqlalchemy import text

            type_filter = f"AND memory_type = '{memory_type}'" if memory_type else ""

            sql = text(f"""
                SELECT id, content, summary, importance, memory_type, metadata, created_at,
                       1 - (embedding <=> :embedding) as similarity
                FROM agent_memories
                WHERE agent_id = :agent_id {type_filter}
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """)

            result = session.execute(sql, {
                'embedding': str(query_embedding),
                'agent_id': str(self.agent_id),
                'limit': limit
            })

            memories = []
            for row in result:
                memories.append({
                    'id': str(row.id),
                    'content': row.content,
                    'summary': row.summary,
                    'importance': row.importance,
                    'memory_type': row.memory_type,
                    'metadata': row.metadata,
                    'similarity': row.similarity,
                    'created_at': row.created_at.isoformat()
                })

            session.close()
            return memories
        except Exception as e:
            print(f"Error retrieving memories for {self.name}: {e}")
            return []

    def add_to_short_term_memory(self, human_message: str, ai_message: str):
        """Add exchange to short-term conversation memory."""
        self.short_term_memory.save_context(
            {"input": human_message},
            {"output": ai_message}
        )

    def get_short_term_context(self) -> str:
        """Get short-term memory context as string."""
        return self.short_term_memory.load_memory_variables({}).get('chat_history', '')

    def clear_short_term_memory(self):
        """Clear short-term memory."""
        self.short_term_memory.clear()

    @abstractmethod
    async def process(self, state: AgentState) -> AgentResponse:
        """Process the current state and return a response.

        This method must be implemented by all agents.

        Args:
            state: Current agent state with messages, context, etc.

        Returns:
            AgentResponse with the agent's output
        """
        pass

    def _build_context(self, state: AgentState) -> str:
        """Build context string from state and memories."""
        context_parts = [
            f"Task: {state['task']}",
            f"\nConversation History:",
        ]

        for msg in state['messages'][-5:]:  # Last 5 messages
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            context_parts.append(f"  {role}: {content}")

        task_context = state.get('task_context') or {}
        if task_context:
            rag_context = task_context.get('rag_context')
            rag_sources = task_context.get('rag_sources')
            if rag_context:
                context_parts.append("\nRelevant Document Context:\n" + rag_context)
            if rag_sources:
                context_parts.append(f"\nDocument Sources: {rag_sources}")
            # Include any remaining context keys
            extra_context = {
                key: value
                for key, value in task_context.items()
                if key not in {'rag_context', 'rag_results', 'rag_sources'}
            }
            if extra_context:
                context_parts.append(f"\nAdditional Context: {extra_context}")

        if state.get('results'):
            context_parts.append("\nPrevious Agent Results:")
            for result in state['results']:
                context_parts.append(f"  - {result.get('agent_name', 'unknown')}: {result.get('summary', '')}")

        return "\n".join(context_parts)

    async def _call_llm(self, messages: List[Any]) -> str:
        """Call the LLM with given messages."""
        response = await self.llm.ainvoke(messages)
        return response.content

    def get_capabilities_description(self) -> str:
        """Get a formatted description of agent capabilities."""
        return f"{self.display_name}: {self.description}\nCapabilities: {', '.join(self.capabilities)}"
