"""Django settings for FiboTask project."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# SECURITY: never commit real secrets; configure via environment.
# In production (DEBUG off) a missing SECRET_KEY is a hard boot error,
# never a silent fallback to the dev key.
_DEV_KEY = "django-insecure-dev-only-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_KEY)

DEBUG = _env_bool("DEBUG", True)

if not DEBUG and (not os.environ.get("SECRET_KEY") or SECRET_KEY == _DEV_KEY):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is off.")

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "FiboTask.urls"

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

WSGI_APPLICATION = "FiboTask.wsgi.application"


# Database: SQLite locally, Postgres (or anything) in prod via DATABASE_URL.
# Example: DATABASE_URL=postgres://postgres:1010@localhost:5432/todo_db
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    try:
        import dj_database_url

        DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
    except ImportError:
        raise ImportError("DATABASE_URL is set but dj-database-url is not installed.")
else:
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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Production hardening (active whenever DEBUG is off, e.g. on Render).
# WhiteNoise serves static files; the manifest storage adds hashed names
# so updated CSS/JS/favicons never stick in caches.
if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Deliberately NOT enabling HSTS / forced HTTPS redirect yet: Render
    # terminates TLS at its proxy and the MVP shares one SQLite database.
    # Revisit both when accounts + Postgres land.

# DoS guard for the Fibonacci generator (?n=...).
try:
    FIBONACCI_MAX_TERMS = max(1, int(os.environ.get("FIBONACCI_MAX_TERMS", "1000")))
except ValueError:
    FIBONACCI_MAX_TERMS = 1000

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
