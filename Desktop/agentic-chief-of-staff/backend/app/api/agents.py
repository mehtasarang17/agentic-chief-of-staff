"""Agents API endpoints."""
import uuid
from flask import Blueprint, request, jsonify

from app.models.database import db_session, Agent, AgentMemory
from app.utils.logger import get_logger

bp = Blueprint('agents', __name__)
logger = get_logger(__name__)


@bp.route('', methods=['GET'])
@bp.route('/', methods=['GET'])
def list_agents():
    """List all registered agents."""
    session = db_session()
    try:
        agents = session.query(Agent).filter(Agent.is_active == True).all()

        return jsonify({
            'agents': [
                {
                    'id': str(agent.id),
                    'name': agent.name,
                    'display_name': agent.display_name,
                    'description': agent.description,
                    'agent_type': agent.agent_type,
                    'capabilities': agent.capabilities,
                    'is_active': agent.is_active
                }
                for agent in agents
            ]
        })

    finally:
        session.close()


@bp.route('/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get details of a specific agent."""
    session = db_session()
    try:
        agent = session.query(Agent).filter(
            Agent.id == uuid.UUID(agent_id)
        ).first()

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        # Get memory stats
        memory_count = session.query(AgentMemory).filter(
            AgentMemory.agent_id == agent.id
        ).count()

        return jsonify({
            'id': str(agent.id),
            'name': agent.name,
            'display_name': agent.display_name,
            'description': agent.description,
            'agent_type': agent.agent_type,
            'capabilities': agent.capabilities,
            'system_prompt': agent.system_prompt,
            'config': agent.config,
            'is_active': agent.is_active,
            'memory_count': memory_count,
            'created_at': agent.created_at.isoformat(),
            'updated_at': agent.updated_at.isoformat()
        })

    finally:
        session.close()


@bp.route('/<agent_id>/memories', methods=['GET'])
def get_agent_memories(agent_id):
    """Get memories for a specific agent."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    memory_type = request.args.get('type')

    session = db_session()
    try:
        agent = session.query(Agent).filter(
            Agent.id == uuid.UUID(agent_id)
        ).first()

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        query = session.query(AgentMemory).filter(
            AgentMemory.agent_id == agent.id
        )

        if memory_type:
            query = query.filter(AgentMemory.memory_type == memory_type)

        total = query.count()
        memories = query.order_by(
            AgentMemory.created_at.desc()
        ).offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            'memories': [
                {
                    'id': str(mem.id),
                    'memory_type': mem.memory_type,
                    'content': mem.content,
                    'summary': mem.summary,
                    'importance': mem.importance,
                    'access_count': mem.access_count,
                    'metadata': mem.metadata_,
                    'created_at': mem.created_at.isoformat(),
                    'last_accessed': mem.last_accessed.isoformat() if mem.last_accessed else None
                }
                for mem in memories
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


@bp.route('/<agent_id>/memories', methods=['DELETE'])
def clear_agent_memories(agent_id):
    """Clear all memories for an agent."""
    session = db_session()
    try:
        agent = session.query(Agent).filter(
            Agent.id == uuid.UUID(agent_id)
        ).first()

        if not agent:
            return jsonify({'error': 'Agent not found'}), 404

        deleted = session.query(AgentMemory).filter(
            AgentMemory.agent_id == agent.id
        ).delete()

        session.commit()

        return jsonify({
            'message': f'Cleared {deleted} memories for agent {agent.display_name}'
        })

    finally:
        session.close()


@bp.route('/stats', methods=['GET'])
def get_agent_stats():
    """Get statistics for all agents."""
    session = db_session()
    try:
        from sqlalchemy import func

        stats = []
        agents = session.query(Agent).all()

        for agent in agents:
            memory_stats = session.query(
                AgentMemory.memory_type,
                func.count(AgentMemory.id).label('count')
            ).filter(
                AgentMemory.agent_id == agent.id
            ).group_by(AgentMemory.memory_type).all()

            stats.append({
                'agent_id': str(agent.id),
                'agent_name': agent.name,
                'display_name': agent.display_name,
                'agent_type': agent.agent_type,
                'is_active': agent.is_active,
                'memory_breakdown': {
                    stat.memory_type: stat.count for stat in memory_stats
                },
                'total_memories': sum(stat.count for stat in memory_stats)
            })

        return jsonify({'agent_stats': stats})

    finally:
        session.close()
