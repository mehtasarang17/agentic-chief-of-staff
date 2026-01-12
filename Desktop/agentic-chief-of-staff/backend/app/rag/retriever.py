"""RAG Retriever for context enhancement."""
from typing import List, Dict, Any, Optional

from app.rag.vector_store import VectorStore
from app.config import settings


class RAGRetriever:
    """
    RAG Retriever that enhances queries with relevant document context.
    """

    def __init__(self):
        self.vector_store = VectorStore()

    async def retrieve_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        max_chunks: int = 5,
        similarity_threshold: float = 0.7,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for a query.

        Args:
            query: User query
            user_id: Optional user ID for filtering
            max_chunks: Maximum number of chunks to retrieve
            similarity_threshold: Minimum similarity score
            include_metadata: Whether to include chunk metadata

        Returns:
            Dict with context and metadata
        """
        # Search for relevant chunks
        chunks = await self.vector_store.similarity_search(
            query=query,
            k=max_chunks,
            filter_document_ids=document_ids,
            filter_user_id=user_id,
            similarity_threshold=similarity_threshold
        )

        if not chunks:
            return {
                'has_context': False,
                'context': '',
                'sources': [],
                'chunks': []
            }

        # Build context string
        context_parts = []
        sources = []
        seen_sources = set()

        for chunk in chunks:
            context_parts.append(f"[Source: {chunk['filename']}]\n{chunk['content']}")

            # Track unique sources
            source_key = f"{chunk['document_id']}-{chunk['filename']}"
            if source_key not in seen_sources:
                sources.append({
                    'document_id': chunk['document_id'],
                    'filename': chunk['filename'],
                    'file_type': chunk['file_type'],
                    'similarity': chunk['similarity']
                })
                seen_sources.add(source_key)

        context = "\n\n---\n\n".join(context_parts)

        return {
            'has_context': True,
            'context': context,
            'sources': sources,
            'chunks': chunks if include_metadata else [],
            'total_chunks': len(chunks)
        }

    async def retrieve_with_reranking(
        self,
        query: str,
        user_id: Optional[str] = None,
        initial_k: int = 10,
        final_k: int = 5,
        diversity_factor: float = 0.3
    ) -> Dict[str, Any]:
        """
        Retrieve context with reranking for better relevance and diversity.

        Args:
            query: User query
            user_id: Optional user ID
            initial_k: Initial number of candidates
            final_k: Final number after reranking
            diversity_factor: Weight for diversity (0-1)

        Returns:
            Dict with reranked context
        """
        # Get initial candidates
        chunks = await self.vector_store.similarity_search(
            query=query,
            k=initial_k,
            filter_user_id=user_id,
            similarity_threshold=0.5
        )

        if not chunks:
            return {
                'has_context': False,
                'context': '',
                'sources': [],
                'chunks': []
            }

        # Simple MMR-style reranking for diversity
        selected_chunks = []
        remaining_chunks = chunks.copy()

        while len(selected_chunks) < final_k and remaining_chunks:
            if not selected_chunks:
                # First chunk is most similar
                selected_chunks.append(remaining_chunks.pop(0))
            else:
                # Score remaining chunks by similarity - redundancy
                best_chunk = None
                best_score = -1

                for chunk in remaining_chunks:
                    similarity_score = chunk['similarity']

                    # Calculate max redundancy with selected chunks
                    max_redundancy = max(
                        self._calculate_redundancy(chunk['content'], sel['content'])
                        for sel in selected_chunks
                    )

                    # Combined score
                    score = (1 - diversity_factor) * similarity_score - diversity_factor * max_redundancy

                    if score > best_score:
                        best_score = score
                        best_chunk = chunk

                if best_chunk:
                    selected_chunks.append(best_chunk)
                    remaining_chunks.remove(best_chunk)

        # Build context
        context_parts = [f"[Source: {c['filename']}]\n{c['content']}" for c in selected_chunks]

        return {
            'has_context': True,
            'context': "\n\n---\n\n".join(context_parts),
            'sources': [
                {
                    'document_id': c['document_id'],
                    'filename': c['filename'],
                    'similarity': c['similarity']
                }
                for c in selected_chunks
            ],
            'chunks': selected_chunks
        }

    def _calculate_redundancy(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap redundancy."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def get_document_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of a specific document."""
        from app.models.database import db_session, Document, DocumentChunk

        session = db_session()
        try:
            document = session.query(Document).filter(
                Document.id == document_id
            ).first()

            if not document:
                return None

            chunks = session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).order_by(DocumentChunk.chunk_index).all()

            return {
                'id': str(document.id),
                'filename': document.original_filename,
                'file_type': document.file_type,
                'file_size': document.file_size,
                'status': document.processing_status,
                'chunk_count': len(chunks),
                'preview': chunks[0].content[:500] if chunks else '',
                'created_at': document.created_at.isoformat()
            }
        finally:
            session.close()
