"""WebSocket handlers for real-time communication."""
import uuid
import asyncio
from flask_socketio import emit, join_room, leave_room

from app.agents.graph import run_agent_workflow
from app.rag.retriever import RAGRetriever
from app.models.database import db_session, Conversation, Message
from app.utils.logger import get_logger

logger = get_logger(__name__)
rag_retriever = RAGRetriever()


def register_handlers(socketio):
    """Register WebSocket event handlers."""

    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info(f"Client connected: {request.sid if hasattr(request, 'sid') else 'unknown'}")
        emit('connected', {'status': 'connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        logger.info(f"Client disconnected")

    @socketio.on('join_conversation')
    def handle_join(data):
        """Join a conversation room for real-time updates."""
        conversation_id = data.get('conversation_id')
        if conversation_id:
            join_room(conversation_id)
            emit('joined', {'conversation_id': conversation_id})

    @socketio.on('leave_conversation')
    def handle_leave(data):
        """Leave a conversation room."""
        conversation_id = data.get('conversation_id')
        if conversation_id:
            leave_room(conversation_id)
            emit('left', {'conversation_id': conversation_id})

    @socketio.on('message')
    def handle_message(data):
        """Handle incoming chat message with streaming response."""
        message = data.get('message')
        conversation_id = data.get('conversation_id')
        use_rag = data.get('use_rag', True)

        if not message:
            emit('error', {'message': 'Message is required'})
            return

        # Create or get conversation
        session = db_session()
        try:
            if conversation_id:
                conversation = session.query(Conversation).filter(
                    Conversation.id == uuid.UUID(conversation_id)
                ).first()
            else:
                conversation = Conversation(
                    title=message[:50] + '...' if len(message) > 50 else message
                )
                session.add(conversation)
                session.flush()
                conversation_id = str(conversation.id)

            # Store user message
            user_msg = Message(
                conversation_id=conversation.id,
                role='user',
                content=message
            )
            session.add(user_msg)
            session.commit()

            # Emit acknowledgment
            emit('message_received', {
                'conversation_id': conversation_id,
                'message_id': str(user_msg.id)
            })

            # Get conversation history
            history = session.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.created_at).all()

            messages = [
                {'role': msg.role, 'content': msg.content}
                for msg in history
            ]

            # Emit thinking status
            emit('agent_status', {
                'status': 'thinking',
                'agent': 'orchestrator',
                'message': 'Analyzing your request...'
            }, room=conversation_id)

            # Get RAG context
            context = {}
            if use_rag:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                rag_result = loop.run_until_complete(
                    rag_retriever.retrieve_context(message)
                )
                if rag_result['has_context']:
                    context['rag_results'] = rag_result['chunks']
                    context['rag_context'] = rag_result['context']

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
            assistant_msg = Message(
                conversation_id=conversation.id,
                role='assistant',
                content=result['response'],
                agent_name=result.get('agent_name'),
                agent_thoughts=result.get('thoughts'),
                tool_calls=result.get('tool_calls')
            )
            session.add(assistant_msg)
            session.commit()

            # Emit response
            emit('response', {
                'conversation_id': conversation_id,
                'message_id': str(assistant_msg.id),
                'content': result['response'],
                'agent': result.get('agent_name'),
                'thoughts': result.get('thoughts', []),
                'tool_calls': result.get('tool_calls', []),
                'is_final': result.get('is_final', True),
                'needs_clarification': result.get('needs_clarification', False)
            }, room=conversation_id)

            # Emit completion
            emit('agent_status', {
                'status': 'completed',
                'agent': result.get('agent_name'),
                'message': 'Response generated'
            }, room=conversation_id)

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            emit('error', {'message': str(e)})
        finally:
            session.close()

    @socketio.on('typing')
    def handle_typing(data):
        """Broadcast typing indicator."""
        conversation_id = data.get('conversation_id')
        if conversation_id:
            emit('user_typing', {
                'conversation_id': conversation_id,
                'is_typing': data.get('is_typing', False)
            }, room=conversation_id, include_self=False)


# Import request for WebSocket context
from flask import request
