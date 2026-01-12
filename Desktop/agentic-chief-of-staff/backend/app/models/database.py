"""Database models and session management."""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, Integer, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session
from pgvector.sqlalchemy import Vector

from app.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Create session factory
session_factory = sessionmaker(bind=engine)
db_session = scoped_session(session_factory)

# Base class for models
Base = declarative_base()
Base.query = db_session.query_property()


class User(Base):
    """User model for authentication and preferences."""
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    preferences = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    """Conversation session model."""
    __tablename__ = 'conversations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    title = Column(String(255), default="New Conversation")
    summary = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """Individual message in a conversation."""
    __tablename__ = 'messages'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system, agent
    content = Column(Text, nullable=False)
    agent_name = Column(String(100), nullable=True)  # Which agent generated this message
    agent_thoughts = Column(JSON, nullable=True)  # Agent reasoning/planning steps
    tool_calls = Column(JSON, nullable=True)  # Tools used by the agent
    metadata_ = Column("metadata", JSON, default=dict)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Agent(Base):
    """Registered agent model."""
    __tablename__ = 'agents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    agent_type = Column(String(50), nullable=False)  # master, worker
    capabilities = Column(ARRAY(String), default=[])
    system_prompt = Column(Text, nullable=True)
    config = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    memories = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")


class AgentMemory(Base):
    """Long-term memory for agents using vector embeddings."""
    __tablename__ = 'agent_memories'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.id', ondelete='CASCADE'), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True)
    memory_type = Column(String(50), nullable=False)  # episodic, semantic, procedural
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    importance = Column(Float, default=0.5)  # 0-1 scale
    embedding = Column(Vector(1536), nullable=True)  # OpenAI embedding dimension
    metadata_ = Column("metadata", JSON, default=dict)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="memories")


class Document(Base):
    """Uploaded document for RAG."""
    __tablename__ = 'documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash
    processing_status = Column(String(50), default='pending')  # pending, processing, completed, failed
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """Document chunks for RAG vector search."""
    __tablename__ = 'document_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)  # page number, section, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")


class TaskExecution(Base):
    """Track agent task executions."""
    __tablename__ = 'task_executions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    agent_name = Column(String(100), nullable=False)
    task_type = Column(String(100), nullable=False)
    task_description = Column(Text, nullable=True)
    status = Column(String(50), default='pending')  # pending, running, completed, failed
    input_data = Column(JSON, default={})
    output_data = Column(JSON, default={})
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """Get database session context manager."""
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
