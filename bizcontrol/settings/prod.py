from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY == "dev-unsafe-secret-key":
    raise RuntimeError("SECRET_KEY deve ser definido no ambiente de producao.")

ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost"]
