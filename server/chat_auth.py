import logging
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from server.app import db
from server.models import Bot, ChatUser

logger = logging.getLogger(__name__)

chat_auth_bp = Blueprint("chat_auth", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sso_flags():
    """Return dict with SSO provider availability flags for templates."""
    return {
        "google_enabled": bool(current_app.config.get("GOOGLE_CLIENT_ID")),
        "keycloak_enabled": bool(current_app.config.get("KEYCLOAK_CLIENT_ID")),
    }


def _ensure_public_bots(user):
    """Add any active public bots that the user doesn't have yet."""
    public_bots = Bot.query.filter_by(is_active=True, is_public=True).all()
    current_bot_ids = {b.id for b in user.bots}
    added = False
    for bot in public_bots:
        if bot.id not in current_bot_ids:
            user.bots.append(bot)
            added = True
    if added:
        db.session.commit()


def _resolve_sso_user(email, provider, provider_id, first_name, last_name):
    """
    Find or create a ChatUser from SSO callback data.

    Resolution order:
    1. Lookup by provider-specific ID (google_id or keycloak_id) -> return existing
    2. Lookup by email -> link provider ID, return existing
    3. No match -> auto-create new user
    """
    provider_id_field = f"{provider}_id"  # "google_id" or "keycloak_id"

    # Step 1: Find by provider ID
    user = ChatUser.query.filter(
        getattr(ChatUser, provider_id_field) == provider_id
    ).first()
    if user:
        if not user.email and email:
            user.email = email
            db.session.commit()
        _ensure_public_bots(user)
        return user

    # Step 2: Find by email (account linking)
    user = ChatUser.query.filter_by(email=email).first()
    if user:
        setattr(user, provider_id_field, provider_id)
        db.session.commit()
        _ensure_public_bots(user)
        return user

    # Step 3: Auto-create
    base_username = email.split("@")[0].lower().replace(".", "_")
    username = base_username
    counter = 1
    while ChatUser.query.filter_by(username=username).first():
        username = f"{base_username}_{counter}"
        counter += 1

    user = ChatUser(
        username=username,
        email=email,
        password_hash=None,
        auth_provider=provider,
        first_name=first_name or "",
        last_name=last_name or "",
    )
    setattr(user, provider_id_field, provider_id)

    # Assign public bots
    user.bots = Bot.query.filter_by(is_active=True, is_public=True).all()

    db.session.add(user)
    db.session.commit()

    from server.auth import audit_log
    audit_log("sso", "auto_create_user", username, f"provider={provider}, email={email}")

    return user


# ---------------------------------------------------------------------------
# Local login / logout
# ---------------------------------------------------------------------------

@chat_auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("chat_user_id"):
        return redirect(url_for("chat_views.chat_page"))

    flags = _sso_flags()

    if request.method == "POST":
        login_input = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Lookup by username first, then by email
        user = ChatUser.query.filter_by(username=login_input).first()
        if not user and "@" in login_input:
            user = ChatUser.query.filter_by(email=login_input).first()

        if user and user.is_blocked:
            return render_template("chat_login.html", error="Аккаунт заблокирован", **flags)

        if user and user.password_hash and check_password_hash(user.password_hash, password):
            session["chat_user_id"] = user.id
            session["chat_username"] = user.username
            return redirect(url_for("chat_views.chat_page"))

        if user and not user.password_hash:
            return render_template(
                "chat_login.html",
                error="Для этого аккаунта не задан пароль. Используйте SSO или обратитесь к администратору.",
                **flags,
            )

        return render_template("chat_login.html", error="Неверные учётные данные", **flags)

    return render_template("chat_login.html", error=None, **flags)


@chat_auth_bp.route("/logout")
def logout():
    session.pop("chat_user_id", None)
    session.pop("chat_username", None)
    return redirect(url_for("chat_auth.login_page"))


# ---------------------------------------------------------------------------
# Google OAuth2
# ---------------------------------------------------------------------------

@chat_auth_bp.route("/google/login")
def google_login():
    from server.oauth import oauth
    redirect_uri = url_for("chat_auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@chat_auth_bp.route("/google/callback")
def google_callback():
    from server.oauth import oauth
    flags = _sso_flags()

    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        logger.error("Google OAuth error: %s", e)
        return render_template("chat_login.html", error="Ошибка авторизации через Google", **flags)

    userinfo = token.get("userinfo") or oauth.google.userinfo()
    email = (userinfo.get("email") or "").lower()
    google_id = userinfo.get("sub")

    if not email:
        return render_template("chat_login.html", error="Google не предоставил email", **flags)

    # Domain validation
    allowed_domains = current_app.config.get("GOOGLE_ALLOWED_DOMAINS", [])
    if allowed_domains:
        domain = email.split("@")[1] if "@" in email else ""
        if domain not in allowed_domains:
            return render_template("chat_login.html", error="Домен email не разрешён", **flags)

    user = _resolve_sso_user(
        email=email,
        provider="google",
        provider_id=google_id,
        first_name=userinfo.get("given_name", ""),
        last_name=userinfo.get("family_name", ""),
    )

    if not user:
        return render_template("chat_login.html", error="Не удалось создать аккаунт", **flags)
    if user.is_blocked:
        return render_template("chat_login.html", error="Аккаунт заблокирован", **flags)

    session["chat_user_id"] = user.id
    session["chat_username"] = user.username
    return redirect(url_for("chat_views.chat_page"))


# ---------------------------------------------------------------------------
# Keycloak OIDC
# ---------------------------------------------------------------------------

@chat_auth_bp.route("/keycloak/login")
def keycloak_login():
    from server.oauth import oauth
    redirect_uri = url_for("chat_auth.keycloak_callback", _external=True)
    return oauth.keycloak.authorize_redirect(redirect_uri)


@chat_auth_bp.route("/keycloak/callback")
def keycloak_callback():
    from server.oauth import oauth
    flags = _sso_flags()

    try:
        token = oauth.keycloak.authorize_access_token()
    except Exception as e:
        logger.error("Keycloak OAuth error: %s", e)
        return render_template("chat_login.html", error="Ошибка авторизации через ERP", **flags)

    userinfo = token.get("userinfo") or oauth.keycloak.userinfo()
    email = (userinfo.get("email") or "").lower()
    keycloak_id = userinfo.get("sub")

    if not email:
        return render_template("chat_login.html", error="Keycloak не предоставил email", **flags)

    user = _resolve_sso_user(
        email=email,
        provider="keycloak",
        provider_id=keycloak_id,
        first_name=userinfo.get("given_name", ""),
        last_name=userinfo.get("family_name", ""),
    )

    if not user:
        return render_template("chat_login.html", error="Не удалось создать аккаунт", **flags)
    if user.is_blocked:
        return render_template("chat_login.html", error="Аккаунт заблокирован", **flags)

    session["chat_user_id"] = user.id
    session["chat_username"] = user.username
    return redirect(url_for("chat_views.chat_page"))


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def chat_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user_id = session.get("chat_user_id")
        if not user_id:
            return redirect(url_for("chat_auth.login_page"))
        user = db.session.get(ChatUser, user_id)
        if not user or user.is_blocked:
            session.pop("chat_user_id", None)
            return redirect(url_for("chat_auth.login_page"))
        request.chat_user = user
        return f(*args, **kwargs)

    return wrapper
