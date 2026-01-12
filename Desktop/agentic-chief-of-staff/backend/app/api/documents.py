"""Documents API endpoints for RAG."""
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify
import asyncio

from app.config import settings
from app.models.database import db_session, Document, DocumentChunk
from app.rag.document_processor import DocumentProcessor
from app.rag.retriever import RAGRetriever
from app.utils.logger import get_logger

bp = Blueprint('documents', __name__)
logger = get_logger(__name__)
document_processor = DocumentProcessor()
rag_retriever = RAGRetriever()


@bp.route('', methods=['GET'])
@bp.route('/', methods=['GET'])
def list_documents():
    """List all documents."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')

    session = db_session()
    try:
        query = session.query(Document)

        if status:
            query = query.filter(Document.processing_status == status)

        total = query.count()
        documents = query.order_by(
            Document.created_at.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        items = []
        for doc in documents:
            chunk_count = session.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).count()

            items.append({
                'id': str(doc.id),
                'filename': doc.original_filename,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'status': doc.processing_status,
                'chunk_count': chunk_count,
                'metadata': doc.metadata_,
                'created_at': doc.created_at.isoformat()
            })

        return jsonify({
            'documents': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })

    finally:
        session.close()


@bp.route('', methods=['POST'])
@bp.route('/', methods=['POST'])
def upload_document():
    """Upload and process a document."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not document_processor.is_supported(file.filename):
        return jsonify({
            'error': f'Unsupported file type. Supported: {", ".join(document_processor.SUPPORTED_EXTENSIONS.keys())}'
        }), 400

    try:
        # Save file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, unique_filename)

        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        file.save(file_path)

        # Process document
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        document = loop.run_until_complete(
            document_processor.process_file(
                file_path=file_path,
                original_filename=filename,
                metadata={'uploaded_via': 'api'}
            )
        )
        loop.close()

        return jsonify({
            'id': str(document.id),
            'filename': document.original_filename,
            'file_type': document.file_type,
            'file_size': document.file_size,
            'status': document.processing_status,
            'chunk_count': document.metadata_.get('chunk_count', 0),
            'message': 'Document uploaded and processed successfully'
        }), 201

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get document details."""
    session = db_session()
    try:
        document = session.query(Document).filter(
            Document.id == uuid.UUID(document_id)
        ).first()

        if not document:
            return jsonify({'error': 'Document not found'}), 404

        chunks = session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).order_by(DocumentChunk.chunk_index).all()

        return jsonify({
            'id': str(document.id),
            'filename': document.original_filename,
            'file_type': document.file_type,
            'file_size': document.file_size,
            'status': document.processing_status,
            'metadata': document.metadata_,
            'created_at': document.created_at.isoformat(),
            'chunks': [
                {
                    'id': str(chunk.id),
                    'index': chunk.chunk_index,
                    'content': chunk.content,
                    'metadata': chunk.metadata_
                }
                for chunk in chunks
            ]
        })

    finally:
        session.close()


@bp.route('/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a document and its chunks."""
    session = db_session()
    try:
        document = session.query(Document).filter(
            Document.id == uuid.UUID(document_id)
        ).first()

        if not document:
            return jsonify({'error': 'Document not found'}), 404

        # Delete file
        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # Delete document (chunks cascade)
        session.delete(document)
        session.commit()

        return jsonify({'message': 'Document deleted successfully'})

    finally:
        session.close()


@bp.route('/search', methods=['POST'])
def search_documents():
    """Search documents using RAG."""
    data = request.get_json()

    if not data or not data.get('query'):
        return jsonify({'error': 'Query is required'}), 400

    query = data['query']
    max_results = data.get('max_results', 5)
    threshold = data.get('threshold', 0.7)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            rag_retriever.retrieve_context(
                query=query,
                max_chunks=max_results,
                similarity_threshold=threshold
            )
        )
        loop.close()

        return jsonify({
            'query': query,
            'has_results': results['has_context'],
            'results': results['chunks'],
            'sources': results['sources']
        })

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return jsonify({'error': str(e)}), 500
