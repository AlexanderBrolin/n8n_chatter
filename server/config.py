import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://n8n_front:n8n_front@localhost:5432/n8n_front",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "static", "uploads")
    )

    # Google OAuth2
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_ALLOWED_DOMAINS = [
        d.strip()
        for d in os.environ.get("GOOGLE_ALLOWED_DOMAINS", "").split(",")
        if d.strip()
    ]

    # Web Push (VAPID)
    # docker-compose env_file doesn't interpret \n escapes, so convert them
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:admin@example.com")

    # Keycloak OIDC
    KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "")
    KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "master")
    KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "")
    KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")
