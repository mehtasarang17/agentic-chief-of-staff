"""Health check endpoints."""
from flask import Blueprint, jsonify
from datetime import datetime

from app.config import settings

bp = Blueprint('health', __name__)


@bp.route('', methods=['GET'])
@bp.route('/', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': settings.APP_NAME,
        'version': settings.APP_VERSION,
        'timestamp': datetime.utcnow().isoformat()
    })


@bp.route('/ready', methods=['GET'])
def readiness_check():
    """Readiness check including dependencies."""
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'openai': check_openai()
    }

    all_healthy = all(c['status'] == 'healthy' for c in checks.values())

    return jsonify({
        'status': 'ready' if all_healthy else 'not_ready',
        'checks': checks,
        'timestamp': datetime.utcnow().isoformat()
    }), 200 if all_healthy else 503


def check_database():
    """Check database connection."""
    try:
        from app.models.database import db_session
        from sqlalchemy import text
        session = db_session()
        session.execute(text('SELECT 1'))
        session.close()
        return {'status': 'healthy'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}


def check_redis():
    """Check Redis connection."""
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        return {'status': 'healthy'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}


def check_openai():
    """Check OpenAI API key is configured."""
    if settings.OPENAI_API_KEY and len(settings.OPENAI_API_KEY) > 10:
        return {'status': 'healthy'}
    return {'status': 'unhealthy', 'error': 'API key not configured'}
