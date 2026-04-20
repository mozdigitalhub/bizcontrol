import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def get_env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in ["1", "true", "yes", "on"]


def get_env_list(name, default=None):
    if default is None:
        default = []
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def get_env_int(name, default=0):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-unsafe-secret-key")
DEBUG = get_env_bool("DEBUG", False)
ALLOWED_HOSTS = get_env_list("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = get_env_list("CSRF_TRUSTED_ORIGINS", [])
CORS_ALLOWED_ORIGINS = get_env_list(
    "CORS_ALLOWED_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"]
)
CORS_ALLOW_CREDENTIALS = True

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = get_env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = get_env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = get_env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "BizControl <no-reply@bizcontrol.app>",
)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = get_env_int("EMAIL_TIMEOUT", 20)
EMAIL_BRAND_LOGO_URL = os.environ.get("EMAIL_BRAND_LOGO_URL", "").strip()
TENANT_REQUIRE_BUSINESS_SELECTION = get_env_bool(
    "TENANT_REQUIRE_BUSINESS_SELECTION", False
)
SESSION_INACTIVITY_TIMEOUT = get_env_int("SESSION_INACTIVITY_TIMEOUT", 300)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "tenants",
    "accounts",
    "catalog",
    "inventory",
    "customers",
    "sales",
    "quotations",
    "deliveries",
    "receivables",
    "billing",
    "finance",
    "reports",
    "food",
    "superadmin",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.SessionInactivityMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "tenants.middleware.BusinessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "bizcontrol.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "tenants.context_processors.current_business",
            ],
            "libraries": {
                "pagination_tags": "tenants.templatetags.pagination_tags",
            },
        },
    },
]

WSGI_APPLICATION = "bizcontrol.wsgi.application"

db_default = f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"
DATABASES = {
    "default": dj_database_url.config(default=db_default, conn_max_age=600),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "pt-pt"
TIME_ZONE = "Africa/Maputo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

USE_SPACES = get_env_bool("USE_SPACES", False)

if USE_SPACES:
    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")

    SPACES_ACCESS_KEY = os.environ.get("SPACES_ACCESS_KEY", os.environ.get("AWS_ACCESS_KEY_ID", "")).strip()
    SPACES_SECRET_KEY = os.environ.get("SPACES_SECRET_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY", "")).strip()
    SPACES_BUCKET_NAME = os.environ.get(
        "SPACES_BUCKET_NAME", os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    ).strip()
    SPACES_REGION = os.environ.get("SPACES_REGION", os.environ.get("AWS_S3_REGION_NAME", "")).strip()
    SPACES_ENDPOINT_URL = os.environ.get(
        "SPACES_ENDPOINT_URL",
        f"https://{SPACES_REGION}.digitaloceanspaces.com" if SPACES_REGION else "",
    ).strip()
    SPACES_CUSTOM_DOMAIN = os.environ.get("SPACES_CUSTOM_DOMAIN", "").strip()
    SPACES_LOCATION = os.environ.get("SPACES_LOCATION", "media").strip("/")
    SPACES_QUERYSTRING_AUTH = get_env_bool("SPACES_QUERYSTRING_AUTH", False)
    SPACES_FILE_OVERWRITE = get_env_bool("SPACES_FILE_OVERWRITE", False)

    missing_spaces_vars = []
    if not SPACES_ACCESS_KEY:
        missing_spaces_vars.append("SPACES_ACCESS_KEY")
    if not SPACES_SECRET_KEY:
        missing_spaces_vars.append("SPACES_SECRET_KEY")
    if not SPACES_BUCKET_NAME:
        missing_spaces_vars.append("SPACES_BUCKET_NAME")
    if not SPACES_REGION:
        missing_spaces_vars.append("SPACES_REGION")
    if not SPACES_ENDPOINT_URL:
        missing_spaces_vars.append("SPACES_ENDPOINT_URL")
    if missing_spaces_vars:
        raise RuntimeError(
            "USE_SPACES=True, mas faltam variaveis: "
            + ", ".join(missing_spaces_vars)
        )

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": SPACES_ACCESS_KEY,
                "secret_key": SPACES_SECRET_KEY,
                "bucket_name": SPACES_BUCKET_NAME,
                "region_name": SPACES_REGION,
                "endpoint_url": SPACES_ENDPOINT_URL,
                "default_acl": None,
                "querystring_auth": SPACES_QUERYSTRING_AUTH,
                "file_overwrite": SPACES_FILE_OVERWRITE,
                "location": SPACES_LOCATION,
            },
        },
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }

    if SPACES_CUSTOM_DOMAIN:
        if SPACES_LOCATION:
            MEDIA_URL = f"https://{SPACES_CUSTOM_DOMAIN}/{SPACES_LOCATION}/"
        else:
            MEDIA_URL = f"https://{SPACES_CUSTOM_DOMAIN}/"
    else:
        if SPACES_LOCATION:
            MEDIA_URL = (
                f"{SPACES_ENDPOINT_URL.rstrip('/')}/{SPACES_BUCKET_NAME}/{SPACES_LOCATION}/"
            )
        else:
            MEDIA_URL = f"{SPACES_ENDPOINT_URL.rstrip('/')}/{SPACES_BUCKET_NAME}/"
    MEDIA_ROOT = BASE_DIR / "media"
    SERVE_MEDIA = False
else:
    MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
    MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))
    SERVE_MEDIA = get_env_bool("SERVE_MEDIA", DEBUG)

LOGIN_REDIRECT_URL = "reports:dashboard"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("DRF_ANON_RATE", "20/min"),
        "tenant_register": os.environ.get("DRF_TENANT_REGISTER_RATE", "5/hour"),
    },
}
