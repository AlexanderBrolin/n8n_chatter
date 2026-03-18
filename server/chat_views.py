from flask import Blueprint, render_template, request

from server.chat_auth import chat_login_required

chat_views_bp = Blueprint("chat_views", __name__)


@chat_views_bp.route("/")
@chat_login_required
def chat_page():
    return render_template("chat.html", user=request.chat_user)
