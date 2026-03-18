from functools import wraps

import click
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from server.app import db
from server.models import AdminUser, AuditLog

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("admin_logged_in"):
        return redirect(url_for("views.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        admin = AdminUser.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session["admin_logged_in"] = True
            session["admin_username"] = username
            session["admin_id"] = admin.id
            return redirect(url_for("views.dashboard"))
        return render_template("login.html", error="Неверные учётные данные")
    return render_template("login.html", error=None)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))


# --- Decorators ---


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)

    return wrapper


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("auth.login_page"))
        admin = get_current_admin()
        if not admin or not admin.is_superadmin:
            flash("Доступ только для суперадминистраторов.", "error")
            return redirect(url_for("views.dashboard"))
        return f(*args, **kwargs)

    return wrapper


def get_current_admin():
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    return db.session.get(AdminUser, admin_id)


# --- Audit helper ---


def audit_log(actor, action, target, details=""):
    entry = AuditLog(actor=actor, action=action, target=target, details=details)
    db.session.add(entry)
    db.session.commit()


# --- CLI command to create admin ---


@auth_bp.cli.command("create-admin")
@click.argument("username")
@click.password_option()
def create_admin_cmd(username, password):
    """Создать администратора платформы."""
    existing = AdminUser.query.filter_by(username=username).first()
    if existing:
        click.echo(f"Админ '{username}' уже существует.")
        return
    admin = AdminUser(
        username=username,
        password_hash=generate_password_hash(password),
        is_superadmin=True,
    )
    db.session.add(admin)
    db.session.commit()
    click.echo(f"Админ '{username}' создан (суперадмин).")
