"""These settings rely on various environment variables being set
"""

import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost taleggio.local").split()

TEST = "test" in sys.argv or "pytest" in sys.argv[0]
DEBUG = bool(os.environ.get("DEBUG", False))

SERVER_EMAIL = "contact@bustimes.org"
DEFAULT_FROM_EMAIL = "bustimes.org <contact@bustimes.org>"

if TEST:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
else:
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True
    EMAIL_TIMEOUT = 10

INSTALLED_APPS = [
    "accounts",
    "busstops",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "bustimes",
    "disruptions",
    "fares",
    "vehicles",
    "vosa",
    "email_obfuscator",
    "channels",
    "api",
    "rest_framework",
    "django_filters",
    "simple_history",
    "huey.contrib.djhuey",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "busstops.middleware.WhiteNoiseWithFallbackMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# Stadia Maps tiles require we send at least the origin in cross-origin requests.
# For same-origin requests, the full referrer is useful (e.g. for the contact form)
SECURE_REFERRER_POLICY = "origin-when-cross-origin"

CSRF_TRUSTED_ORIGINS = ["https://bustimes.org"]

if DEBUG and "runserver" in sys.argv:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "debug_toolbar_force.middleware.ForceDebugToolbarMiddleware",
    ]

    # Docker
    import socket

    _, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]

ROOT_URLCONF = "buses.urls"

ASGI_APPLICATION = "vehicles.routing.application"


DATABASES = {"default": dj_database_url.config(conn_max_age=None)}

DATABASES["default"]["options"] = {
    "application_name": os.environ.get("APPLICATION_NAME") or " ".join(sys.argv)[-63:],
    "connect_timeout": 9,
}

DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES["default"]["TEST"] = {"SERIALIZE": False}
DATABASES["default"]["ENGINE"] = "django.contrib.gis.db.backends.postgis"
if DEBUG and "runserver" in sys.argv:
    del DATABASES["default"]["CONN_MAX_AGE"]  # reset to the default (0)

# TEST_RUNNER = "django_slowtests.testrunner.DiscoverSlowestTestsRunner"
# NUM_SLOW_TESTS = 10

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "/vehicles"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

if os.environ.get("READ_ONLY_DB_HOST"):
    REPLICA_DATABASES = []
    for i, host in enumerate(os.environ["READ_ONLY_DB_HOST"].split()):
        key = f"read-only-{i}"
        DATABASES[key] = DATABASES["default"].copy()
        DATABASES[key]["HOST"] = host
        REPLICA_DATABASES.append(key)
    DATABASE_ROUTERS = ["multidb.PinningReplicaRouter"]
    MIDDLEWARE.append("busstops.middleware.pin_db_middleware")
    READ_DATABASE = key
else:
    READ_DATABASE = "default"

DATA_UPLOAD_MAX_MEMORY_SIZE = None
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

REDIS_URL = os.environ.get("REDIS_URL")

HUEY = {
    "immediate": DEBUG or TEST,
    "connection": {
        "url": REDIS_URL,
    },
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL], "expiry": 20},
    }
}


STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR.parent / "bustimes-static")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_ROOT = BASE_DIR / "busstops" / "static" / "root"
TEMPLATE_MINIFER_STRIP_FUNCTION = "buses.utils.minify"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "debug": DEBUG or TEST,
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    ["template_minifier.template.loaders.app_directories.Loader"],
                )
            ],
        },
    }
]
if DEBUG:
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        "django.template.loaders.app_directories.Loader"
    ]
elif TEST:
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        (
            "django.template.loaders.cached.Loader",
            ["django.template.loaders.app_directories.Loader"],
        )
    ]


if TEST:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
elif DEBUG:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
elif REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

    SESSION_ENGINE = "django.contrib.sessions.backends.cache"


VARNISH_HOST = os.environ.get("VARNISH_HOST")
VARNISH_PORT = os.environ.get("VARNISH_PORT")
if VARNISH_HOST and VARNISH_PORT:
    VARNISH = (VARNISH_HOST, int(VARNISH_PORT))
else:
    VARNISH = None


TIME_FORMAT = "H:i"
DATE_FORMAT = "l j F Y"
# DATETIME_FORMAT = "j M H:i"
TIME_ZONE = "Europe/London"
USE_TZ = True
USE_I18N = False
LANGUAGE_CODE = "en-gb"
USE_L10N = False  # force use of TIME_FORMAT, DATE_FORMAT etc. Alas, deprecated


if TEST:
    pass
elif not DEBUG and "collectstatic" not in sys.argv and "SENTRY_DSN" in os.environ:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import ignore_logger
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        integrations=[DjangoIntegration(), RedisIntegration()],
        ignore_errors=[KeyboardInterrupt, RuntimeError],
        release=os.environ.get("COMMIT_HASH"),
        traces_sample_rate=0.001,
    )
    ignore_logger("django.security.DisallowedHost")

if not TEST:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
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

TFL = {  # London
    "app_id": os.environ.get("TFL_APP_ID"),
    "app_key": os.environ.get("TFL_APP_KEY"),
}
TFWM = {  # West Midlands
    "app_id": os.environ.get("TFWM_APP_ID"),
    "app_key": os.environ.get("TFWM_APP_KEY"),
}
NTA_API_KEY = os.environ.get("NTA_API_KEY")  # Ireland
NTA_OPERATORS = {
    "Bus Éireann",
    "Dublin Bus",
    "Expressway",
    "Go-Ahead Ireland",
    "Go-Ahead Commuter",
}

DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR:
    DATA_DIR = Path(DATA_DIR)
else:
    DATA_DIR = BASE_DIR / "data"
TNDS_DIR = DATA_DIR / "TNDS"

AKISMET_API_KEY = os.environ.get("AKISMET_API_KEY")
AKISMET_SITE_URL = "https://bustimes.org"
