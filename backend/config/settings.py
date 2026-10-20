"""
Django settings for iBilik CRM.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _ensure_item(values: list[str], item: str) -> list[str]:
    if item in values:
        return values
    return [*values, item]


PRODUCTION_HOST = "ibilik.dckwebgen.com"
PRODUCTION_ORIGIN = "https://ibilik.dckwebgen.com"

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-&v0f+j90t6$rwpmlo^1=dm@lm30jh2c83woql21&zw(tgid*0o",
)

DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = _ensure_item(
    _env_list(
        "DJANGO_ALLOWED_HOSTS",
        [PRODUCTION_HOST, "localhost", "127.0.0.1", "testserver"],
    ),
    PRODUCTION_HOST,
)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "accounts.apps.AccountsConfig",
    "crm.apps.CrmConfig",
    "pipeline.apps.PipelineConfig",
    "cases.apps.CasesConfig",
    "payments.apps.PaymentsConfig",
    "quotes.apps.QuotesConfig",
    "bookings.apps.BookingsConfig",
    "locations.apps.LocationsConfig",
    "match.apps.MatchConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}

CORS_ALLOWED_ORIGINS = _ensure_item(
    _env_list(
        "DJANGO_CORS_ALLOWED_ORIGINS",
        [PRODUCTION_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    ),
    PRODUCTION_ORIGIN,
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

CSRF_TRUSTED_ORIGINS = _ensure_item(
    _env_list(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        [PRODUCTION_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    ),
    PRODUCTION_ORIGIN,
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_NAME = "csrftoken"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

WEBSITE_INGEST_API_KEY = os.environ.get("WEBSITE_INGEST_API_KEY", "")
WHATSAPP_INGEST_API_KEY = os.environ.get("WHATSAPP_INGEST_API_KEY") or WEBSITE_INGEST_API_KEY
FACEBOOK_INGEST_API_KEY = os.environ.get("FACEBOOK_INGEST_API_KEY") or WEBSITE_INGEST_API_KEY
WHATSAPP_PROVIDER = os.environ.get(
    "WHATSAPP_PROVIDER",
    "test" if DEBUG and not os.environ.get("WHATSAPP_ACCESS_TOKEN") else "meta",
)
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")
FACEBOOK_PROVIDER = os.environ.get(
    "FACEBOOK_PROVIDER",
    "test" if DEBUG and not os.environ.get("FACEBOOK_ACCESS_TOKEN") else "meta",
)
FACEBOOK_ACCESS_TOKEN = os.environ.get("FACEBOOK_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")
FACEBOOK_VERIFY_TOKEN = os.environ.get("FACEBOOK_VERIFY_TOKEN", "")
FACEBOOK_APP_SECRET = os.environ.get("FACEBOOK_APP_SECRET", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
