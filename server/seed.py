import click
from werkzeug.security import generate_password_hash

from server.app import db
from server.models import AdminUser


def register_cli(app):
    @app.cli.command("seed")
    @click.option("--username", default="admin", help="Имя администратора")
    @click.option("--password", default="admin", help="Пароль администратора")
    def seed_cmd(username, password):
        """Создать начального администратора если его нет."""
        existing = AdminUser.query.filter_by(username=username).first()
        if existing:
            click.echo(f"Админ '{username}' уже существует, пропускаем.")
            return
        admin = AdminUser(
            username=username,
            password_hash=generate_password_hash(password),
            is_superadmin=True,
        )
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Создан админ '{username}' / '{password}' (суперадмин).")
