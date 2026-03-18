import os

from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class="server.config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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

    @app.route("/")
    def root():
        from flask import redirect, url_for
        return redirect(url_for("chat_views.chat_page"))

    from server.sse import sse_broker
    sse_broker.init_app(app)

    with app.app_context():
        db.create_all()
        os.makedirs(app.config.get("UPLOAD_FOLDER", "server/static/uploads"), exist_ok=True)

        # Auto-seed default admin if none exists
        from server.models import AdminUser
        from werkzeug.security import generate_password_hash

        if not AdminUser.query.first():
            admin = AdminUser(
                username="admin",
                password_hash=generate_password_hash("admin"),
                is_superadmin=True,
            )
            db.session.add(admin)
            db.session.commit()

    from server.seed import register_cli

    register_cli(app)

    return app
