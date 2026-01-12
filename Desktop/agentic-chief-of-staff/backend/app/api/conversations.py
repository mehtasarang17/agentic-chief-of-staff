"""Conversations API endpoints."""
import uuid
from datetime import datetime
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file
import markdown
from xhtml2pdf import pisa

from app.models.database import db_session, Conversation, Message
from app.utils.logger import get_logger

bp = Blueprint('conversations', __name__)
logger = get_logger(__name__)


@bp.route('', methods=['GET'])
@bp.route('/', methods=['GET'])
def list_conversations():
    """List all conversations with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)  # Max 100 per page

    session = db_session()
    try:
        # Get total count
        total = session.query(Conversation).count()

        # Get paginated conversations
        conversations = session.query(Conversation).order_by(
            Conversation.updated_at.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        items = []
        for conv in conversations:
            # Get message count
            message_count = session.query(Message).filter(
                Message.conversation_id == conv.id
            ).count()

            # Get last message preview
            last_message = session.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at.desc()).first()

            items.append({
                'id': str(conv.id),
                'title': conv.title,
                'summary': conv.summary,
                'message_count': message_count,
                'last_message': last_message.content[:100] if last_message else None,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat()
            })

        return jsonify({
            'conversations': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })

    finally:
        session.close()


@bp.route('/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """Get a specific conversation with messages."""
    session = db_session()
    try:
        conversation = session.query(Conversation).filter(
            Conversation.id == uuid.UUID(conversation_id)
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Get all messages
        messages = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).all()

        return jsonify({
            'id': str(conversation.id),
            'title': conversation.title,
            'summary': conversation.summary,
            'metadata': conversation.metadata_,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
            'messages': [
                {
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'agent_name': msg.agent_name,
                    'thoughts': msg.agent_thoughts,
                    'tool_calls': msg.tool_calls,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ]
        })

    finally:
        session.close()


@bp.route('', methods=['POST'])
@bp.route('/', methods=['POST'])
def create_conversation():
    """Create a new conversation."""
    data = request.get_json() or {}

    session = db_session()
    try:
        conversation = Conversation(
            title=data.get('title', 'New Conversation'),
            metadata_=data.get('metadata', {})
        )
        session.add(conversation)
        session.commit()

        return jsonify({
            'id': str(conversation.id),
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat()
        }), 201

    finally:
        session.close()


@bp.route('/<conversation_id>', methods=['PUT'])
def update_conversation(conversation_id):
    """Update a conversation."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    session = db_session()
    try:
        conversation = session.query(Conversation).filter(
            Conversation.id == uuid.UUID(conversation_id)
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        if 'title' in data:
            conversation.title = data['title']
        if 'summary' in data:
            conversation.summary = data['summary']
        if 'metadata' in data:
            conversation.metadata_ = data['metadata']

        conversation.updated_at = datetime.utcnow()
        session.commit()

        return jsonify({
            'id': str(conversation.id),
            'title': conversation.title,
            'summary': conversation.summary,
            'updated_at': conversation.updated_at.isoformat()
        })

    finally:
        session.close()


@bp.route('/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages."""
    session = db_session()
    try:
        conversation = session.query(Conversation).filter(
            Conversation.id == uuid.UUID(conversation_id)
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        # Delete conversation (messages cascade)
        session.delete(conversation)
        session.commit()

        return jsonify({'message': 'Conversation deleted successfully'}), 200

    finally:
        session.close()


@bp.route('/<conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    """Get messages for a conversation with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    session = db_session()
    try:
        conversation = session.query(Conversation).filter(
            Conversation.id == uuid.UUID(conversation_id)
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        total = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).count()

        messages = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        return jsonify({
            'messages': [
                {
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'agent_name': msg.agent_name,
                    'thoughts': msg.agent_thoughts,
                    'tool_calls': msg.tool_calls,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in messages
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        })

    finally:
        session.close()


def _build_conversation_pdf(conversation: Conversation, messages: list[Message]) -> BytesIO:
    """Render a conversation transcript to PDF."""
    title = conversation.title or "Conversation Transcript"
    parts = []
    for msg in messages:
        role = msg.role.capitalize()
        agent = f" ({msg.agent_name})" if msg.agent_name else ""
        timestamp = msg.created_at.isoformat()
        content_html = markdown.markdown(msg.content or "", extensions=["fenced_code", "tables"])
        parts.append(
            f"""
            <div class="message {msg.role}">
              <div class="meta">{role}{agent} · {timestamp}</div>
              <div class="content">{content_html}</div>
            </div>
            """
        )

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {{ font-family: Arial, sans-serif; color: #0f172a; }}
          h1 {{ font-size: 20px; margin-bottom: 8px; }}
          .subtitle {{ font-size: 12px; color: #475569; margin-bottom: 16px; }}
          .message {{ margin-bottom: 16px; padding: 10px; border: 1px solid #e2e8f0; border-radius: 6px; }}
          .message.user {{ background: #eff6ff; }}
          .message.assistant {{ background: #f8fafc; }}
          .meta {{ font-size: 11px; color: #475569; margin-bottom: 6px; }}
          .content {{ font-size: 12px; line-height: 1.5; }}
          code {{ background: #e2e8f0; padding: 2px 4px; border-radius: 4px; }}
          pre {{ background: #0f172a; color: #f8fafc; padding: 8px; border-radius: 6px; }}
        </style>
      </head>
      <body>
        <h1>{title}</h1>
        <div class="subtitle">Conversation ID: {conversation.id}</div>
        {''.join(parts)}
      </body>
    </html>
    """

    pdf_buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=pdf_buffer)
    if result.err:
        raise ValueError("Failed to generate PDF.")
    pdf_buffer.seek(0)
    return pdf_buffer


@bp.route('/<conversation_id>/export/pdf', methods=['GET'])
def export_conversation_pdf(conversation_id):
    """Export a conversation transcript as PDF."""
    session = db_session()
    try:
        conversation = session.query(Conversation).filter(
            Conversation.id == uuid.UUID(conversation_id)
        ).first()

        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        messages = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at).all()

        pdf_buffer = _build_conversation_pdf(conversation, messages)
        filename = f"conversation-{conversation.id}.pdf"
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    finally:
        session.close()
