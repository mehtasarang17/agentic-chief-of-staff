"""Main Flask application factory."""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

from app.config import settings
from app.models.database import init_db
from app.api import chat, agents, documents, conversations, health
from app.utils.logger import setup_logging

# Initialize SocketIO globally
socketio = SocketIO(cors_allowed_origins="*", async_mode='gevent')


def create_app() -> Flask:
    """Create and configure the Flask application."""

    # Setup logging
    setup_logging()

    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = settings.SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = settings.MAX_CONTENT_LENGTH

    # CORS setup
    CORS(app, resources={
        r"/api/*": {
            "origins": settings.CORS_ORIGINS.split(","),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })

    # Initialize database
    init_db()

    # Register blueprints
    app.register_blueprint(health.bp, url_prefix='/health')
    app.register_blueprint(chat.bp, url_prefix='/api/chat')
    app.register_blueprint(agents.bp, url_prefix='/api/agents')
    app.register_blueprint(documents.bp, url_prefix='/api/documents')
    app.register_blueprint(conversations.bp, url_prefix='/api/conversations')

    # Initialize SocketIO
    socketio.init_app(app)

    # Register WebSocket handlers
    from app.api.websocket import register_handlers
    register_handlers(socketio)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app


# For development
if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=9001, debug=True)
