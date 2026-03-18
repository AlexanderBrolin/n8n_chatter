import json
import logging
import queue
import threading
from collections import defaultdict

import redis

logger = logging.getLogger(__name__)


class SSEBroker:
    """Redis-backed pub/sub broker for Server-Sent Events.

    Each Gunicorn worker maintains local queues for its SSE connections.
    Publishing goes through Redis so all workers receive the message.
    """

    def __init__(self):
        self._listeners = defaultdict(list)
        self._user_listeners = defaultdict(list)
        self._lock = threading.Lock()
        self._redis = None
        self._pubsub = None
        self._thread = None

    def init_app(self, app):
        """Initialize Redis connection from Flask app config."""
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.Redis.from_url(redis_url)
        self._start_listener()

    def _start_listener(self):
        """Start background thread that listens to Redis pub/sub."""
        self._pubsub = self._redis.pubsub()
        self._pubsub.psubscribe("sse:conv:*", "sse:user:*")
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        """Background loop: receive Redis messages, dispatch to local queues."""
        for msg in self._pubsub.listen():
            if msg["type"] not in ("pmessage",):
                continue
            try:
                channel = msg["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()

                if channel.startswith("sse:conv:"):
                    conv_id = int(channel.split(":", 2)[2])
                    self._dispatch_conv(conv_id, data)
                elif channel.startswith("sse:user:"):
                    user_id = int(channel.split(":", 2)[2])
                    self._dispatch_user(user_id, data)
            except Exception:
                logger.exception("Error processing Redis pub/sub message")

    def _dispatch_conv(self, conversation_id, data):
        """Push data to all local queues subscribed to this conversation."""
        with self._lock:
            dead = []
            for q in self._listeners.get(conversation_id, []):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                try:
                    self._listeners[conversation_id].remove(q)
                except ValueError:
                    pass

    def _dispatch_user(self, user_id, data):
        """Push data to all local queues subscribed to this user."""
        with self._lock:
            dead = []
            for q in self._user_listeners.get(user_id, []):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                try:
                    self._user_listeners[user_id].remove(q)
                except ValueError:
                    pass

    # --- Per-conversation subscriptions ---

    def subscribe(self, conversation_id):
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._listeners[conversation_id].append(q)
        return q

    def unsubscribe(self, conversation_id, q):
        with self._lock:
            try:
                self._listeners[conversation_id].remove(q)
            except ValueError:
                pass
            if not self._listeners[conversation_id]:
                del self._listeners[conversation_id]

    def publish(self, conversation_id, data):
        """Publish message to a conversation channel via Redis."""
        payload = json.dumps(data, ensure_ascii=False)
        if self._redis:
            self._redis.publish(f"sse:conv:{conversation_id}", payload)
        else:
            # Fallback: direct dispatch (no Redis)
            self._dispatch_conv(conversation_id, payload)

    # --- Per-user subscriptions ---

    def subscribe_user(self, user_id):
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._user_listeners[user_id].append(q)
        return q

    def unsubscribe_user(self, user_id, q):
        with self._lock:
            try:
                self._user_listeners[user_id].remove(q)
            except ValueError:
                pass
            if not self._user_listeners[user_id]:
                del self._user_listeners[user_id]

    def publish_user(self, user_id, event_type, data):
        """Publish a named event to user's SSE stream via Redis."""
        payload = json.dumps(data, ensure_ascii=False)
        msg = f"event: {event_type}\ndata: {payload}\n\n"
        if self._redis:
            self._redis.publish(f"sse:user:{user_id}", msg)
        else:
            self._dispatch_user(user_id, msg)


sse_broker = SSEBroker()
