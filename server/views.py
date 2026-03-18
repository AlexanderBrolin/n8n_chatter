import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from server.app import db
from server.auth import audit_log, login_required
from server.models import AdminUser, AuditLog, Bot, ChatUser, Conversation, Message, QuickReply, user_bot_access

views_bp = Blueprint("views", __name__)


# --- Dashboard ---


@views_bp.route("/")
@login_required
def dashboard():
    stats = {
        "bots": Bot.query.count(),
        "bots_active": Bot.query.filter_by(is_active=True).count(),
        "users": ChatUser.query.count(),
        "messages": Message.query.count(),
        "conversations": Conversation.query.count(),
    }
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()
    return render_template("admin/dashboard.html", stats=stats, recent_logs=recent_logs)


# --- Bots ---


@views_bp.route("/bots")
@login_required
def bots():
    page = request.args.get("page", 1, type=int)
    pagination = Bot.query.order_by(Bot.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template("admin/bots.html", bots=pagination)


@views_bp.route("/bots/new", methods=["GET", "POST"])
@login_required
def bot_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        description = request.form.get("description", "").strip()
        webhook_url = request.form.get("webhook_url", "").strip()

        if not name or not username:
            flash("Заполните все обязательные поля.", "error")
            return render_template("admin/bot_edit.html", bot=None)

        if Bot.query.filter_by(username=username).first():
            flash(f"Бот с именем '{username}' уже существует.", "error")
            return render_template("admin/bot_edit.html", bot=None)

        from server.auth import get_current_admin

        admin = get_current_admin()
        bot = Bot(
            name=name,
            username=username,
            description=description,
            webhook_url=webhook_url,
            api_token=uuid.uuid4().hex + uuid.uuid4().hex,
            created_by=admin.username if admin else "",
        )
        db.session.add(bot)
        db.session.commit()
        audit_log(
            admin.username if admin else "system",
            "create_bot",
            bot.username,
            f"Бот '{bot.name}' создан",
        )
        flash(f"Бот '{bot.name}' создан. Токен: {bot.api_token}", "success")
        return redirect(url_for("views.bot_edit", bot_id=bot.id))

    return render_template("admin/bot_edit.html", bot=None)


@views_bp.route("/bots/<int:bot_id>", methods=["GET", "POST"])
@login_required
def bot_edit(bot_id):
    bot = db.session.get(Bot, bot_id)
    if not bot:
        flash("Бот не найден.", "error")
        return redirect(url_for("views.bots"))

    if request.method == "POST":
        bot.name = request.form.get("name", bot.name).strip()
        bot.description = request.form.get("description", "").strip()
        bot.webhook_url = request.form.get("webhook_url", bot.webhook_url).strip()
        bot.avatar_url = request.form.get("avatar_url", "").strip()
        db.session.commit()

        from server.auth import get_current_admin

        admin = get_current_admin()
        audit_log(
            admin.username if admin else "system",
            "update_bot",
            bot.username,
        )
        flash("Бот обновлён.", "success")
        return redirect(url_for("views.bot_edit", bot_id=bot.id))

    return render_template("admin/bot_edit.html", bot=bot)


@views_bp.route("/bots/<int:bot_id>/action", methods=["POST"])
@login_required
def bot_action(bot_id):
    bot = db.session.get(Bot, bot_id)
    if not bot:
        flash("Бот не найден.", "error")
        return redirect(url_for("views.bots"))

    action = request.form.get("action")
    from server.auth import get_current_admin

    admin = get_current_admin()
    actor = admin.username if admin else "system"

    if action == "toggle":
        bot.is_active = not bot.is_active
        db.session.commit()
        status = "активирован" if bot.is_active else "деактивирован"
        audit_log(actor, "toggle_bot", bot.username, status)
        flash(f"Бот {status}.", "success")
    elif action == "regenerate_token":
        bot.api_token = uuid.uuid4().hex + uuid.uuid4().hex
        db.session.commit()
        audit_log(actor, "regenerate_token", bot.username)
        flash(f"Новый токен: {bot.api_token}", "success")
    elif action == "delete":
        db.session.delete(bot)
        db.session.commit()
        audit_log(actor, "delete_bot", bot.username)
        flash("Бот удалён.", "success")
        return redirect(url_for("views.bots"))

    return redirect(url_for("views.bot_edit", bot_id=bot.id))


# --- Users ---


@views_bp.route("/users")
@login_required
def users():
    page = request.args.get("page", 1, type=int)
    pagination = ChatUser.query.order_by(ChatUser.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template("admin/users.html", users=pagination)


@views_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def user_new():
    all_bots = Bot.query.order_by(Bot.name).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        bot_ids = request.form.getlist("bot_ids", type=int)

        if not username or not password:
            flash("Логин и пароль обязательны.", "error")
            return render_template("admin/user_edit.html", user=None, all_bots=all_bots)

        if ChatUser.query.filter_by(username=username).first():
            flash(f"Пользователь '{username}' уже существует.", "error")
            return render_template("admin/user_edit.html", user=None, all_bots=all_bots)

        user = ChatUser(
            username=username,
            password_hash=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
        )
        if bot_ids:
            user.bots = Bot.query.filter(Bot.id.in_(bot_ids)).all()
        db.session.add(user)
        db.session.commit()

        from server.auth import get_current_admin

        admin = get_current_admin()
        audit_log(
            admin.username if admin else "system",
            "create_user",
            username,
        )
        flash(f"Пользователь '{username}' создан.", "success")
        return redirect(url_for("views.users"))

    return render_template("admin/user_edit.html", user=None, all_bots=all_bots)


@views_bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@login_required
def user_edit(user_id):
    user = db.session.get(ChatUser, user_id)
    if not user:
        flash("Пользователь не найден.", "error")
        return redirect(url_for("views.users"))

    all_bots = Bot.query.order_by(Bot.name).all()

    if request.method == "POST":
        user.first_name = request.form.get("first_name", "").strip()
        user.last_name = request.form.get("last_name", "").strip()
        new_password = request.form.get("password", "").strip()
        if new_password:
            user.password_hash = generate_password_hash(new_password)
        bot_ids = request.form.getlist("bot_ids", type=int)
        user.bots = Bot.query.filter(Bot.id.in_(bot_ids)).all() if bot_ids else []
        db.session.commit()

        from server.auth import get_current_admin

        admin = get_current_admin()
        audit_log(
            admin.username if admin else "system",
            "update_user",
            user.username,
        )
        flash("Пользователь обновлён.", "success")
        return redirect(url_for("views.user_edit", user_id=user.id))

    return render_template("admin/user_edit.html", user=user, all_bots=all_bots)


@views_bp.route("/users/<int:user_id>/action", methods=["POST"])
@login_required
def user_action(user_id):
    user = db.session.get(ChatUser, user_id)
    if not user:
        flash("Пользователь не найден.", "error")
        return redirect(url_for("views.users"))

    action = request.form.get("action")
    from server.auth import get_current_admin

    admin = get_current_admin()
    actor = admin.username if admin else "system"

    if action == "toggle_block":
        user.is_blocked = not user.is_blocked
        db.session.commit()
        status = "заблокирован" if user.is_blocked else "разблокирован"
        audit_log(actor, "toggle_block_user", user.username, status)
        flash(f"Пользователь {status}.", "success")
    elif action == "delete":
        db.session.delete(user)
        db.session.commit()
        audit_log(actor, "delete_user", user.username)
        flash("Пользователь удалён.", "success")
        return redirect(url_for("views.users"))

    return redirect(url_for("views.user_edit", user_id=user.id))


# --- Audit ---


@views_bp.route("/audit")
@login_required
def audit():
    page = request.args.get("page", 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template("admin/audit.html", logs=logs)


# --- Group Chats ---


@views_bp.route("/group-chats")
@login_required
def group_chats():
    page = request.args.get("page", 1, type=int)
    pagination = Conversation.query.filter_by(chat_type="group").order_by(
        Conversation.updated_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template("admin/group_chats.html", chats=pagination)


@views_bp.route("/group-chats/new", methods=["GET", "POST"])
@login_required
def group_chat_new():
    all_bots = Bot.query.filter_by(is_active=True).order_by(Bot.name).all()
    all_users = ChatUser.query.filter_by(is_blocked=False).order_by(ChatUser.username).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        bot_id = request.form.get("bot_id", type=int)
        member_ids = request.form.getlist("member_ids", type=int)

        if not title or not bot_id or len(member_ids) < 1:
            flash("Заполните все обязательные поля (название, бот, хотя бы 1 участник).", "error")
            return render_template("admin/group_chat_edit.html", chat=None, all_bots=all_bots, all_users=all_users)

        bot = db.session.get(Bot, bot_id)
        if not bot:
            flash("Бот не найден.", "error")
            return render_template("admin/group_chat_edit.html", chat=None, all_bots=all_bots, all_users=all_users)

        members = ChatUser.query.filter(ChatUser.id.in_(member_ids)).all()

        conv = Conversation(
            user_id=members[0].id,
            bot_id=bot.id,
            chat_type="group",
            title=title,
        )
        conv.members = members
        db.session.add(conv)
        db.session.commit()

        from server.auth import get_current_admin

        admin = get_current_admin()
        audit_log(
            admin.username if admin else "system",
            "create_group_chat",
            title,
            f"Бот: {bot.name}, участников: {len(members)}",
        )
        flash(f"Групповой чат '{title}' создан.", "success")
        return redirect(url_for("views.group_chat_edit", chat_id=conv.id))

    return render_template("admin/group_chat_edit.html", chat=None, all_bots=all_bots, all_users=all_users)


@views_bp.route("/group-chats/<int:chat_id>", methods=["GET", "POST"])
@login_required
def group_chat_edit(chat_id):
    conv = db.session.get(Conversation, chat_id)
    if not conv or conv.chat_type != "group":
        flash("Групповой чат не найден.", "error")
        return redirect(url_for("views.group_chats"))

    all_bots = Bot.query.filter_by(is_active=True).order_by(Bot.name).all()
    all_users = ChatUser.query.filter_by(is_blocked=False).order_by(ChatUser.username).all()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "delete":
            title = conv.title
            db.session.delete(conv)
            db.session.commit()
            from server.auth import get_current_admin

            admin = get_current_admin()
            audit_log(admin.username if admin else "system", "delete_group_chat", title)
            flash("Групповой чат удалён.", "success")
            return redirect(url_for("views.group_chats"))

        conv.title = request.form.get("title", conv.title).strip()
        member_ids = request.form.getlist("member_ids", type=int)
        conv.members = ChatUser.query.filter(ChatUser.id.in_(member_ids)).all() if member_ids else []
        if conv.members:
            conv.user_id = conv.members[0].id
        db.session.commit()

        from server.auth import get_current_admin

        admin = get_current_admin()
        audit_log(admin.username if admin else "system", "update_group_chat", conv.title)
        flash("Групповой чат обновлён.", "success")
        return redirect(url_for("views.group_chat_edit", chat_id=conv.id))

    return render_template("admin/group_chat_edit.html", chat=conv, all_bots=all_bots, all_users=all_users)


# --- Quick Replies ---


@views_bp.route("/bots/<int:bot_id>/quick-replies", methods=["POST"])
@login_required
def bot_quick_replies(bot_id):
    bot = db.session.get(Bot, bot_id)
    if not bot:
        flash("Бот не найден.", "error")
        return redirect(url_for("views.bots"))

    action = request.form.get("action")

    if action == "add":
        text = request.form.get("text", "").strip()
        if text:
            order = QuickReply.query.filter_by(bot_id=bot.id).count()
            qr = QuickReply(bot_id=bot.id, text=text, order=order)
            db.session.add(qr)
            db.session.commit()
            flash("Быстрый ответ добавлен.", "success")
    elif action == "delete":
        qr_id = request.form.get("qr_id", type=int)
        qr = db.session.get(QuickReply, qr_id)
        if qr and qr.bot_id == bot.id:
            db.session.delete(qr)
            db.session.commit()
            flash("Быстрый ответ удалён.", "success")

    return redirect(url_for("views.bot_edit", bot_id=bot.id))
