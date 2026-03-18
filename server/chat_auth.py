from functools import wraps

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from server.app import db
from server.models import ChatUser

chat_auth_bp = Blueprint("chat_auth", __name__)


@chat_auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("chat_user_id"):
        return redirect(url_for("chat_views.chat_page"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = ChatUser.query.filter_by(username=username).first()
        if user and not user.is_blocked and check_password_hash(user.password_hash, password):
            session["chat_user_id"] = user.id
            session["chat_username"] = user.username
            return redirect(url_for("chat_views.chat_page"))
        if user and user.is_blocked:
            return render_template("chat_login.html", error="Аккаунт заблокирован")
        return render_template("chat_login.html", error="Неверные учётные данные")
    return render_template("chat_login.html", error=None)


@chat_auth_bp.route("/logout")
def logout():
    session.pop("chat_user_id", None)
    session.pop("chat_username", None)
    return redirect(url_for("chat_auth.login_page"))


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
