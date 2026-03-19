from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_oauth(app):
    """Register Google and Keycloak OAuth providers based on app config."""
    oauth.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    kc_url = app.config.get("KEYCLOAK_URL", "")
    kc_realm = app.config.get("KEYCLOAK_REALM", "master")
    if kc_url and app.config.get("KEYCLOAK_CLIENT_ID"):
        issuer = f"{kc_url.rstrip('/')}/realms/{kc_realm}"
        oauth.register(
            name="keycloak",
            client_id=app.config["KEYCLOAK_CLIENT_ID"],
            client_secret=app.config["KEYCLOAK_CLIENT_SECRET"],
            server_metadata_url=f"{issuer}/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
