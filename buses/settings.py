"""These settings rely on various environment variables being set"""

import os
import sys
from pathlib import Path
from warnings import filterwarnings

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.huey import HueyIntegration
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.integrations.redis import RedisIntegration

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.environ.get(
    "ALLOWED_HOSTS", "[::1] 127.0.0.1 localhost joshuas-macbook-pro.local"
).split()

CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "https://bustimes.org https://staging.bustimes.org https://bustimes-org.fly.dev",
).split()

TEST = "test" in sys.argv or "pytest" in sys.argv[0]
DEBUG = bool(os.environ.get("DEBUG", False))

SERVER_EMAIL = "contact@bustimes.org"
DEFAULT_FROM_EMAIL = "bustimes.org <contact@bustimes.org>"

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_TIMEOUT = 10
if TEST:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

INSTALLED_APPS = [
    # "daphne",
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
    "api",
    "rest_framework",
    "django_filters",
    "simple_history",
    "huey.contrib.djhuey",
    "corsheaders",
    "turnstile",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "busstops.middleware.GZipIfNotStreamingMiddleware",
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

SECURE_BROWSER_XSS_FILTER = True
SECURE_PROXY_SSL_HEADER = ("HTTP_CF_VISITOR", '{"scheme":"https"}')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_REDIRECT_EXEMPT = [r"^version$"]


CORS_ALLOW_ALL_ORIGINS = True
CORS_URLS_REGEX = r"(^\/(api\/|(vehicles|stops)\.json)|.*\/journeys\/.*)"

if DEBUG and "runserver" in sys.argv:
    INSTALLED_APPS += [
        "debug_toolbar",
        "template_profiler_panel",
    ]
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "debug_toolbar_force.middleware.ForceDebugToolbarMiddleware",
    ]
    INTERNAL_IPS = ["127.0.0.1"]
    # DEBUG_TOOLBAR_PANELS = [
    #     "template_profiler_panel.panels.template.TemplateProfilerPanel",
    # ]

ROOT_URLCONF = "buses.urls"

ASGI_APPLICATION = "buses.asgi.application"


DATABASES = {"default": dj_database_url.config(conn_max_age=None)}

DATABASES["default"]["options"] = {
    "application_name": os.environ.get("APPLICATION_NAME") or " ".join(sys.argv)[-63:],
    "connect_timeout": 9,
}

DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES["default"]["TEST"] = {"SERIALIZE": False}
if DEBUG and "runserver" in sys.argv:
    del DATABASES["default"][
        "CONN_MAX_AGE"
    ]  # reset to the default (i.e. no persistent connections)

TEST_RUNNER = "django_slowtests.testrunner.DiscoverSlowestTestsRunner"
NUM_SLOW_TESTS = 10

AUTH_USER_MODEL = "accounts.User"
LOGIN_REDIRECT_URL = "/vehicles"

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

READ_DATABASE = "default"
# if os.environ.get("READ_ONLY_DB_HOST"):
#     REPLICA_DATABASES = []
#     for i, host in enumerate(os.environ["READ_ONLY_DB_HOST"].split()):
#         key = f"read-only-{i}"
#         DATABASES[key] = DATABASES["default"].copy()
#         DATABASES[key]["HOST"] = host
#         REPLICA_DATABASES.append(key)
#     DATABASE_ROUTERS = ["multidb.PinningReplicaRouter"]
#     MIDDLEWARE.append("busstops.middleware.pin_db_middleware")
#     READ_DATABASE = key

DATA_UPLOAD_MAX_MEMORY_SIZE = None
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

REDIS_URL = os.environ.get("REDIS_URL")

HUEY = {
    "name": "bustimes",
    "immediate": DEBUG or TEST,
    "connection": {
        "url": REDIS_URL,
    },
}

STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles")
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
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
                "buses.context_processors.ad",
                "vehicles.context_processors.liveries_css_version",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    ["template_minifier.template.loaders.app_directories.Loader"],
                )
            ],
        },
    },
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": ["busstops/templates/jinja2"],
        "OPTIONS": {
            "environment": "buses.jinja2.environment",
        },
    },
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


CACHES = {}
if TEST or DEBUG:
    CACHES["default"] = {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
# elif DEBUG or not REDIS_URL:
#     CACHES["default"] = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}

if REDIS_URL and not TEST:
    CACHES["redis"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", ""),
    }
    if "default" not in CACHES:
        CACHES["default"] = CACHES["redis"]

        SESSION_ENGINE = "django.contrib.sessions.backends.cache"


TIME_ZONE = "Europe/London"
USE_TZ = True
USE_I18N = False
LANGUAGE_CODE = "en-gb"


# https://adamj.eu/tech/2023/12/07/django-fix-urlfield-assume-scheme-warnings/
filterwarnings(
    "ignore", "The FORMS_URLFIELD_ASSUME_HTTPS transitional setting is deprecated."
)
FORMS_URLFIELD_ASSUME_HTTPS = True


def traces_sampler(context):
    try:
        url = context["wsgi_environ"]["RAW_URI"]
    except KeyError:
        return 0
    if (
        url == "/version"
        or url.startswith("/vehicles.json")
        or url.startswith("/stops.json")
        or url.startswith("/static/")
        or url.startswith("/journeys/")
    ):
        return 0
    if url.startswith("/stops/") or url.startswith("/services/"):
        return 0.004
    if url.startswith("/vehicles"):
        return 0.0005
    return 0.001


if "SENTRY_DSN" in os.environ and not TEST:
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        integrations=[DjangoIntegration(), RedisIntegration(), HueyIntegration()],
        ignore_errors=[KeyboardInterrupt, RuntimeError],
        release=os.environ.get("COMMIT_HASH") or os.environ.get("KAMAL_CONTAINER_NAME"),
    )
    ignore_logger("django.security.DisallowedHost")

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
TFWM_OPERATORS = {
    # "National Express West Midlands",
    # "National Express Coventry",
    # "Diamond Bus",
    # "Landflight",
    # "West Midlands Metro",
    # "Stagecoach Midlands",
}
ACIS_HORIZON_OPERATORS = {
    "Ulsterbus",
    "Ulsterbus Town Services",
    "Translink Metro",
    "Translink Glider",
}
TFE_OPERATORS = {
    "Lothian Buses",
    "Lothian Country Buses",
    "East Coast Buses",
    "Edinburgh Trams",
}

NTA_API_KEY = os.environ.get("NTA_API_KEY")  # Ireland
ALLOW_VEHICLE_NOTES_OPERATORS = (
    "NATX",  # National Express
    "SCLK",  # Scottish Citylink
    "ie-526",  # Irish Citylink
    "ie-1178",  # Dublin Express
)

NEW_VEHICLE_WEBHOOK_URL = os.environ.get("NEW_VEHICLE_WEBHOOK_URL")
STATUS_WEBHOOK_URL = os.environ.get("STATUS_WEBHOOK_URL")

DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR:
    DATA_DIR = Path(DATA_DIR)
else:
    DATA_DIR = BASE_DIR / "data"
TNDS_DIR = DATA_DIR / "TNDS"

TURNSTILE_SITEKEY = os.environ.get("TURNSTILE_SITEKEY", "0x4AAAAAAAFWiyCqdh2c-5sy")
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET")

ABBREVIATE_HOURLY = False
DISABLE_REGISTRATION = True
