from datetime import datetime, timezone

from server.app import db

# --- Association tables ---

user_bot_access = db.Table(
    "user_bot_access",
    db.Column("user_id", db.Integer, db.ForeignKey("chat_users.id"), primary_key=True),
    db.Column("bot_id", db.Integer, db.ForeignKey("bots.id"), primary_key=True),
)

conversation_members = db.Table(
    "conversation_members",
    db.Column("conversation_id", db.Integer, db.ForeignKey("conversations.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("chat_users.id"), primary_key=True),
)


# --- Models ---


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_superadmin = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<AdminUser {self.username}>"


class ChatUser(db.Model):
    __tablename__ = "chat_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    email = db.Column(db.String(256), unique=True, nullable=True)
    auth_provider = db.Column(db.String(20), default="local")
    google_id = db.Column(db.String(256), unique=True, nullable=True)
    keycloak_id = db.Column(db.String(256), unique=True, nullable=True)
    first_name = db.Column(db.String(128), default="")
    last_name = db.Column(db.String(128), default="")
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    bots = db.relationship("Bot", secondary=user_bot_access, back_populates="users")
    conversations = db.relationship("Conversation", back_populates="user")

    def __repr__(self):
        return f"<ChatUser {self.username}>"


class Bot(db.Model):
    __tablename__ = "bots"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    webhook_url = db.Column(db.String(512), nullable=False, default="")
    api_token = db.Column(db.String(256), unique=True, nullable=False)
    avatar_url = db.Column(db.String(512), default="")
    is_public = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    created_by = db.Column(db.String(64), default="")

    users = db.relationship("ChatUser", secondary=user_bot_access, back_populates="bots")
    conversations = db.relationship("Conversation", back_populates="bot")

    def __repr__(self):
        return f"<Bot {self.username}>"


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("chat_users.id"), nullable=False)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), nullable=False)
    chat_type = db.Column(db.String(10), default="private")
    title = db.Column(db.String(256), default="")
    started_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("ChatUser", back_populates="conversations")
    bot = db.relationship("Bot", back_populates="conversations")
    messages = db.relationship(
        "Message", back_populates="conversation", order_by="Message.created_at",
        cascade="all, delete-orphan",
    )
    members = db.relationship(
        "ChatUser", secondary=conversation_members, backref="group_conversations"
    )

    def __repr__(self):
        return f"<Conversation user={self.user_id} bot={self.bot_id}>"

    def user_has_access(self, user):
        if self.user_id == user.id:
            return True
        if self.chat_type == "group":
            return user in self.members
        return False

    def get_all_user_ids(self):
        if self.chat_type == "group":
            return [m.id for m in self.members]
        return [self.user_id]


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id"), nullable=False
    )
    sender_type = db.Column(db.String(10), nullable=False)  # "user" or "bot"
    sender_id = db.Column(db.Integer, nullable=False)
    sender_name = db.Column(db.String(128), default="")
    text = db.Column(db.Text, default="")
    parse_mode = db.Column(db.String(20), default="")  # "markdown", "html", or ""
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    reply_markup = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    conversation = db.relationship("Conversation", back_populates="messages")
    attachments = db.relationship(
        "FileAttachment", back_populates="message", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Message {self.id} [{self.sender_type}]>"


class FileAttachment(db.Model):
    __tablename__ = "file_attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("messages.id"), nullable=False
    )
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(128), default="")
    file_size = db.Column(db.Integer, default=0)
    file_id = db.Column(db.String(128), unique=True, nullable=False)

    message = db.relationship("Message", back_populates="attachments")

    def __repr__(self):
        return f"<FileAttachment {self.filename}>"


class QuickReply(db.Model):
    __tablename__ = "quick_replies"

    id = db.Column(db.Integer, primary_key=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bots.id"), nullable=False)
    text = db.Column(db.String(256), nullable=False)
    order = db.Column(db.Integer, default=0)

    bot = db.relationship("Bot", backref="quick_replies")

    def __repr__(self):
        return f"<QuickReply {self.text[:30]}>"


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("chat_users.id"), nullable=False)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    keys_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("ChatUser", backref="push_subscriptions")

    def __repr__(self):
        return f"<PushSubscription user={self.user_id}>"


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    actor = db.Column(db.String(128), default="")
    action = db.Column(db.String(64), default="")
    target = db.Column(db.String(128), default="")
    details = db.Column(db.Text, default="")

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.actor}>"
