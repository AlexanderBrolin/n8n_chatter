import os

from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class="server.config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    from server.auth import auth_bp
    from server.views import views_bp
    from server.chat_auth import chat_auth_bp
    from server.chat_views import chat_views_bp
    from server.chat_api import chat_api_bp
    from server.bot_api import bot_api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(views_bp, url_prefix="/admin")
    app.register_blueprint(chat_auth_bp, url_prefix="/chat/auth")
    app.register_blueprint(chat_views_bp, url_prefix="/chat")
    app.register_blueprint(chat_api_bp, url_prefix="/chat/api")
    app.register_blueprint(bot_api_bp, url_prefix="/api/bot")

    @app.context_processor
    def inject_admin():
        from server.models import AdminUser

        admin_id = session.get("admin_id")
        if admin_id:
            return {"current_admin": db.session.get(AdminUser, admin_id)}
        return {"current_admin": None}

    from server.sse import sse_broker
    sse_broker.init_app(app)

    with app.app_context():
        db.create_all()
        os.makedirs(app.config.get("UPLOAD_FOLDER", "server/static/uploads"), exist_ok=True)

    from server.seed import register_cli

    register_cli(app)

    return app
