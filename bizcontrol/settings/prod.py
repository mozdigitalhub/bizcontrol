from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY == "dev-unsafe-secret-key":
    raise RuntimeError("SECRET_KEY deve ser definido no ambiente de producao.")

ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost"]

# Reverse proxy settings (DigitalOcean App Platform / similar)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = get_env_bool("USE_X_FORWARDED_HOST", True)
SECURE_SSL_REDIRECT = get_env_bool("SECURE_SSL_REDIRECT", True)

# Secure cookies in production
SESSION_COOKIE_SECURE = get_env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = get_env_bool("CSRF_COOKIE_SECURE", True)

# If not explicitly provided, derive CSRF trusted origins from allowed hosts.
# This avoids CSRF 403 on first production deploy when env var is missing.
if not CSRF_TRUSTED_ORIGINS:
    derived_origins = []
    for host in ALLOWED_HOSTS:
        if not host or host == "*" or host in {"localhost", "127.0.0.1"}:
            continue
        if host.startswith("."):
            derived_origins.append(f"https://*{host}")
        else:
            derived_origins.append(f"https://{host}")
    CSRF_TRUSTED_ORIGINS = derived_origins
