"""Chat API endpoints."""
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
import asyncio

from app.agents.graph import run_agent_workflow
from app.models.database import db_session, Conversation, Message
from app.rag.retriever import RAGRetriever
from app.utils.logger import get_logger

bp = Blueprint('chat', __name__)
logger = get_logger(__name__)
rag_retriever = RAGRetriever()


@bp.route('/message', methods=['POST'])
def send_message():
    """
    Send a message to the Chief of Staff AI.

    Request body:
    {
        "message": "User message",
        "conversation_id": "optional-uuid",
        "use_rag": true,
        "context": {}
    }
    """
    data = request.get_json()

    if not data or not data.get('message'):
        return jsonify({'error': 'Message is required'}), 400

    message = data['message']
    conversation_id = data.get('conversation_id')
    use_rag = data.get('use_rag', True)
    additional_context = data.get('context', {}) or {}
    document_ids = additional_context.get('document_ids')

    session = db_session()

    try:
        # Get or create conversation
        if conversation_id:
            conversation = session.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()

            if not conversation:
                return jsonify({'error': 'Conversation not found'}), 404
        else:
            conversation = Conversation(
                title=message[:50] + '...' if len(message) > 50 else message
            )
            session.add(conversation)
            session.flush()
            conversation_id = str(conversation.id)

        # Store user message
        user_message = Message(
            conversation_id=conversation.id,
            role='user',
            content=message
        )
        session.add(user_message)
        session.commit()

        # Get conversation history
        history = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).all()

        messages = [
            {'role': msg.role, 'content': msg.content, 'agent_name': msg.agent_name}
            for msg in history
        ]

        # Get RAG context if enabled
        context = additional_context.copy()
        if use_rag:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if document_ids:
                rag_result = loop.run_until_complete(
                    rag_retriever.retrieve_context(
                        message,
                        document_ids=document_ids,
                        similarity_threshold=0.2,
                        max_chunks=8
                    )
                )
            else:
                rag_result = loop.run_until_complete(
                    rag_retriever.retrieve_context(message)
                )
            if rag_result['has_context']:
                context['rag_results'] = rag_result['chunks']
                context['rag_context'] = rag_result['context']
                context['rag_sources'] = rag_result['sources']

        # Run agent workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            run_agent_workflow(
                task=message,
                conversation_id=conversation_id,
                messages=messages,
                context=context
            )
        )
        loop.close()

        # Store assistant response
        assistant_message = Message(
            conversation_id=conversation.id,
            role='assistant',
            content=result['response'],
            agent_name=result.get('agent_name'),
            agent_thoughts=result.get('thoughts'),
            tool_calls=result.get('tool_calls'),
            metadata_={
                'is_final': result.get('is_final', True),
                'iteration_count': result.get('iteration_count', 0)
            }
        )
        session.add(assistant_message)

        # Update conversation
        conversation.updated_at = datetime.utcnow()
        session.commit()

        # Build response
        response = {
            'conversation_id': conversation_id,
            'message_id': str(assistant_message.id),
            'response': result['response'],
            'agent': result.get('agent_name', 'unknown'),
            'thoughts': result.get('thoughts', []),
            'tool_calls': result.get('tool_calls', []),
            'is_final': result.get('is_final', True),
            'needs_clarification': result.get('needs_clarification', False),
            'clarification_question': result.get('clarification_question'),
            'sources': context.get('rag_sources', [])
        }

        return jsonify(response), 200

    except Exception as e:
        session.rollback()
        logger.error(f"Error processing message: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@bp.route('/stream', methods=['POST'])
def stream_message():
    """
    Stream a response from the Chief of Staff AI.

    This endpoint returns Server-Sent Events (SSE).
    """
    from flask import Response, stream_with_context

    data = request.get_json()

    if not data or not data.get('message'):
        return jsonify({'error': 'Message is required'}), 400

    def generate():
        # This is a simplified streaming implementation
        # In production, you'd integrate with LangChain's streaming callbacks
        message = data['message']
        conversation_id = data.get('conversation_id', str(uuid.uuid4()))

        yield f"data: {{'type': 'start', 'conversation_id': '{conversation_id}'}}\n\n"

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                run_agent_workflow(
                    task=message,
                    conversation_id=conversation_id,
                    messages=[],
                    context={}
                )
            )
            loop.close()

            # Stream the response in chunks
            response = result['response']
            chunk_size = 50

            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield f"data: {{'type': 'chunk', 'content': '{chunk}'}}\n\n"

            yield f"data: {{'type': 'end', 'agent': '{result.get('agent_name', 'unknown')}'}}\n\n"

        except Exception as e:
            yield f"data: {{'type': 'error', 'message': '{str(e)}'}}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )
