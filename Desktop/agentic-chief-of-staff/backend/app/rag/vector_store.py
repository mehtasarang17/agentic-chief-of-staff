"""Vector store for RAG using pgvector."""
from typing import List, Dict, Any, Optional
import uuid
from sqlalchemy import text

from app.config import settings
from app.models.database import db_session, DocumentChunk, AgentMemory
from langchain_openai import OpenAIEmbeddings


class VectorStore:
    """Vector store for document chunks and agent memories."""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY
        )

    async def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_document_ids: Optional[List[str]] = None,
        filter_user_id: Optional[str] = None,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks using cosine similarity.

        Args:
            query: Search query
            k: Number of results to return
            filter_document_ids: Optional list of document IDs to filter by
            filter_user_id: Optional user ID to filter by
            similarity_threshold: Minimum similarity score

        Returns:
            List of matching chunks with similarity scores
        """
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)

        session = db_session()

        try:
            # Build filter conditions
            filters = []
            params = {
                'embedding': str(query_embedding),
                'limit': k,
                'threshold': similarity_threshold
            }

            if filter_document_ids:
                placeholders = ', '.join([f':doc_id_{i}' for i in range(len(filter_document_ids))])
                filters.append(f"dc.document_id IN ({placeholders})")
                for i, doc_id in enumerate(filter_document_ids):
                    params[f'doc_id_{i}'] = doc_id

            if filter_user_id:
                filters.append("d.user_id = :user_id")
                params['user_id'] = filter_user_id

            where_clause = "WHERE 1=1"
            if filters:
                where_clause += " AND " + " AND ".join(filters)

            # Query with similarity search
            sql = text(f"""
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    dc.metadata,
                    d.original_filename,
                    d.file_type,
                    1 - (dc.embedding <=> :embedding) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                {where_clause}
                AND 1 - (dc.embedding <=> :embedding) >= :threshold
                ORDER BY dc.embedding <=> :embedding
                LIMIT :limit
            """)

            result = session.execute(sql, params)

            chunks = []
            for row in result:
                chunks.append({
                    'id': str(row.id),
                    'document_id': str(row.document_id),
                    'chunk_index': row.chunk_index,
                    'content': row.content,
                    'metadata': row.metadata,
                    'filename': row.original_filename,
                    'file_type': row.file_type,
                    'similarity': float(row.similarity)
                })

            return chunks

        finally:
            session.close()

    async def search_agent_memories(
        self,
        query: str,
        agent_id: str,
        k: int = 5,
        memory_type: Optional[str] = None,
        min_importance: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search agent memories using vector similarity.

        Args:
            query: Search query
            agent_id: Agent ID to search memories for
            k: Number of results
            memory_type: Optional filter by memory type
            min_importance: Minimum importance score

        Returns:
            List of matching memories
        """
        query_embedding = self.embeddings.embed_query(query)

        session = db_session()

        try:
            filters = ["agent_id = :agent_id", "importance >= :min_importance"]
            params = {
                'embedding': str(query_embedding),
                'agent_id': agent_id,
                'min_importance': min_importance,
                'limit': k
            }

            if memory_type:
                filters.append("memory_type = :memory_type")
                params['memory_type'] = memory_type

            where_clause = " AND ".join(filters)

            sql = text(f"""
                SELECT
                    id,
                    memory_type,
                    content,
                    summary,
                    importance,
                    metadata,
                    created_at,
                    1 - (embedding <=> :embedding) as similarity
                FROM agent_memories
                WHERE {where_clause}
                ORDER BY embedding <=> :embedding
                LIMIT :limit
            """)

            result = session.execute(sql, params)

            memories = []
            for row in result:
                memories.append({
                    'id': str(row.id),
                    'memory_type': row.memory_type,
                    'content': row.content,
                    'summary': row.summary,
                    'importance': row.importance,
                    'metadata': row.metadata,
                    'created_at': row.created_at.isoformat(),
                    'similarity': float(row.similarity)
                })

            return memories

        finally:
            session.close()

    async def add_document_chunk(
        self,
        document_id: str,
        content: str,
        chunk_index: int,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Add a document chunk to the vector store."""
        embedding = self.embeddings.embed_query(content)

        session = db_session()
        try:
            chunk = DocumentChunk(
                document_id=uuid.UUID(document_id),
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
                metadata_=metadata or {}
            )
            session.add(chunk)
            session.commit()
            return str(chunk.id)
        finally:
            session.close()

    async def delete_document_chunks(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        session = db_session()
        try:
            result = session.query(DocumentChunk).filter(
                DocumentChunk.document_id == uuid.UUID(document_id)
            ).delete()
            session.commit()
            return result
        finally:
            session.close()
