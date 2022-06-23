"""These settings rely on various environment variables being set
"""

import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost").split()

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
    "antispam",
    "email_obfuscator",
    "channels",
    "api",
    "rest_framework",
    "django_filters",
    "simple_history",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

SECURE_REFERRER_POLICY = None
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

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "bustimes"),
        "CONN_MAX_AGE": None,
        "OPTIONS": {
            "application_name": os.environ.get("APPLICATION_NAME")
            or " ".join(sys.argv)[-63:],
            "connect_timeout": 9,
        },
        "TEST": {"SERIALIZE": False},
    }
}
if DEBUG and "runserver" in sys.argv:
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # reset to the default

TEST_RUNNER = "django_slowtests.testrunner.DiscoverSlowestTestsRunner"
NUM_SLOW_TESTS = 10

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
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CELERY_BROKER_URL], "expiry": 20},
    }
}


STATIC_URL = "/static/"
STATIC_ROOT = os.environ.get("STATIC_ROOT", BASE_DIR.parent / "bustimes-static")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

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
DATETIME_FORMAT = "j M H:i"
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
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.logging import ignore_logger

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
        ignore_errors=[KeyboardInterrupt],
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

DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR:
    DATA_DIR = Path(DATA_DIR)
else:
    DATA_DIR = BASE_DIR / "data"
TNDS_DIR = DATA_DIR / "TNDS"

AKISMET_API_KEY = os.environ.get("AKISMET_API_KEY")
AKISMET_SITE_URL = "https://bustimes.org"

# see bustimes.management.commands.import_passenger
PASSENGER_OPERATORS = [
    (
        "Borders Buses",
        "bordersbuses",
        "S",
        {
            "PERY": "BORD",
            "BB": "BORD",
            "": "PERY",
        },
    ),
    (
        "West Coast Motors",
        "westcoastmotors",
        "S",
        {
            "WCM": "WCMO",
            "GCB": "GCTB",  # Glasgow Citybus
        },
    ),
    (
        "Cardiff Bus",
        "ccts",
        "W",
        {
            "CB": "CBUS",
            # 'NB': '',
        },
    ),
    (
        "Newport Bus",
        "newportbus",
        "W",
        {
            "NTO": "NWPT",
        },
    ),
    (
        "McGill’s",
        "mcgills",
        "S",
        {
            "MCG": "MCGL",
            "McG": "MCGL",
        },
    ),
    (
        "Warrington’s Own Buses",
        "warrington",
        "NW",
        {
            "WOB": "WBTR",
        },
    ),
    (
        "JMB Travel",
        "jmbtravel",
        "S",
        {
            "NJMT": "NJMT",
        },
    ),
    (
        "McColls Travel",
        "mccolls",
        "S",
        {
            "MCLS": "MCLS",
        },
    ),
    (
        "Redline Buses",
        "redline",
        "SE",
        {
            "REDL": "RLNE",
        },
    ),
    (
        "Red Rose Travel",
        "redrose",
        "SE",
        {
            "RRTR": "RRTR",
        },
    ),
    # Reading
    (
        "Reading Buses",
        "readingbuses",
        "SE",
        {
            "RBUS": "RBUS",
        },
    ),
    (
        "Thames Valley Buses",
        "courtney",
        "SE",
        {
            "THVB": "THVB",
            "CTNY": "CTNY",
        },
    ),
    (
        "Newbury & District",
        "kennections",
        "SE",
        {
            "NADS": "NADS",
        },
    ),
    # Go-Ahead
    ("Metrobus", "metrobus", "SE", {"MB": "METR"}),
    # ('Go North East', 'gonortheast', 'NE', {
    #     'GNE': 'GNEL',
    # }),
    (
        "East Yorkshire",
        "eyms",
        "Y",
        {
            "EYMS": "EYMS",
        },
    ),
    # ('Go North West', 'gonorthwest', 'NW', {
    #     'GONW': 'GONW',
    # }),
    (
        "Brighton & Hove Buses",
        "brightonhove",
        "SE",
        {
            "BH": "BHBC",
        },
    ),
]

# see bustimes.management.commands.import_bod
BOD_OPERATORS = [
    ("BEAT", "NW", {}, False),
    ("APTC", "SE", {}, False),
    ("FRNH", "SE", {}, False),
    ("SMMM", "SE", {}, False),
    ("FWAY", "SE", {}, False),
    ("JPCO", "SW", {}, False),
    ("CACC", "Y", {}, False),
    ("SWEY", "Y", {}, False),
    ("WMSA", "EM", {}, False),
    ("LANT", "EM", {}, False),
    ("NWBT", "NW", {}, False),
    ("MARS", "SE", {}, False),
    ("EMBR", "S", {}, False),
    ("NCTR", "EM", {}, False),
    (
        "YCST",
        "NW",
        {
            "LUI": "LNUD",
            "ROS": "ROST",
            "BPT": "BPTR",
            "KDT": "KDTR",
            "HDT": "HRGT",
            "YCD": "YCST",
            "TPEN": "TPEN",
            "FLYE": "FLYE",
            "YACT": "YACT",
        },
        False,
    ),
    (
        "FBOS",
        None,
        {
            "FYOR": "FYOR",
            "FPOT": "FPOT",
            "FSYO": "FSYO",
            "FMAN": "FMAN",
            "FLDS": "FLDS",
            "FSMR": "FSMR",
            "FHUD": "FHUD",
            "FHAL": "FHUD",
            "FBRA": "FBRA",
            "FESX": "FESX",
            "FECS": "FECS",
            "FHDO": "FHDO",
            "FTVA": "FTVA",
            "FHAM": "FHAM",
            "FDOR": "FDOR",
            "FCWL": "FCWL",
            "FBRI": "FBRI",
            "FLEI": "FLEI",
            "RRAR": "RRAR",
            "FBOS": "FBOS",
            "FWYO": "FWYO",
        },
        True,
    ),
    # these no longer operate services - this is just to prevent their TNDS data being used:
    (
        "PTSG",
        None,
        {
            "ABUS": "ABUS",
            "PTSG": "PTSG",
            "MPTR": "MPTR",
            "JOHS": "JOHS",
        },
        False,
    ),
    (
        "TNXB",
        "WM",
        {
            "TNXB": "TNXB",
            "TCVW": "TCVW",
        },
        False,
    ),
    (
        "UNOE",
        "SE",
        {
            "UBN": "UNOE",
            "UNIB": "UNOE",
            "OP": "UNOE",
            "UN": "UNOE",
        },
        False,
    ),
    (
        "TBTN",
        "EM",
        {
            "BRTB": "TBTN",
        },
        False,
    ),
    ("KBUS", "SE", {}, False),
    ("NIBS", "SE", {}, False),
    ("SESX", "EA", {}, True),
    ("STCB", "EA", {}, False),
    ("CSVC", "EA", {"CS": "CSVC"}, False),
    (
        "HIPK",
        "EM",
        {
            "OP": "HIPK",
            "HPB": "HIPK",
        },
        False,
    ),
    ("HNTS", "EM", {}, False),
    # ('SLBS', 'WM', {}, True),
    ("LODG", "SE", {}, False),
    ("FRDS", "SE", {}, False),
    ("AVMT", "SW", {}, False),
    ("BZCO", "SW", {}, False),
    ("C2WI", "SW", {}, False),
    ("CNTY", "SW", {}, False),
    ("COAC", "SW", {}, False),
    ("COTS", "SW", {}, False),
    ("CRYC", "SW", {}, False),
    ("DTCO", "SW", {}, False),
    ("FRMN", "SW", {}, False),
    ("FSRV", "SW", {}, False),
    ("FTZL", "SW", {}, False),
    ("GWIL", "SW", {}, False),
    ("HGCO", "SW", {}, False),
    ("HOPE", "SW", {}, False),
    ("JACK", "SW", {}, False),
    ("LTRV", "SW", {}, False),
    ("NAKL", "SW", {}, False),
    ("OTSS", "SW", {}, False),
    ("PULH", "SW", {}, False),
    ("RIDL", "SW", {}, False),
    ("RSLN", "SW", {}, False),
    ("SMST", "SW", {}, False),
    ("SWCO", "SW", {}, False),
    ("TAWT", "SW", {}, False),
    ("TLYH", "SW", {}, False),
    ("TOTN", "SW", {}, False),
    ("YEOS", "SW", {}, False),
    ("SMMC", "SW", {}, False),
    ("GYLC", "SW", {}, False),
    ("SWAN", "SW", {}, False),
    ("CTCO", "SW", {}, False),
    ("EBLY", "SW", {}, False),
    ("BYCO", "SW", {}, False),
    ("NEJH", "SW", {}, False),
    ("BNNT", "SW", {}, False),
    ("XLBL", "SW", {}, False),
    ("NCSL", "SW", {}, False),
    ("AMKC", "SW", {}, False),
    ("EUTX", "SW", {}, False),
    ("ESTW", "SW", {}, False),
    ("NABC", "SW", {}, False),
    ("QVED", "SW", {}, False),
    ("STAC", "SW", {}, False),
    ("SWOC", "SW", {}, False),
    ("DDLT", "SW", {}, False),
    ("CHCB", "SW", {}, False),
    ("DJWA", "SW", {}, False),
    ("BNSC", "SW", {}, False),
    ("MARC", "SW", {}, False),
    ("NRTL", "SW", {}, False),
    ("PRIC", "SW", {}, False),
    ("LIHO", "SW", {}, False),
    # ('DPCR', 'SW', {}, False),
    ("YCOA", "SW", {}, False),
    ("YELL", "SW", {}, False),
    ("COEV", "SW", {}, False),
    # ('NATX', 'GB', {}, False),
    ("KETR", "SE", {}, False),
    # ('PCCO', 'EM', {}, False),
    ("WGHC", "NE", {}, False),
    ("SPSV", "SE", {}, False),
    ("NVTR", "SE", {}, False),
    ("LEMN", "SE", {}, False),
    ("CHLK", "SE", {}, False),
    ("GOCH", "SE", {"GO": "GOCH"}, False),
    # ('LAKC', 'WM', {}, True),  # incomplete
    (
        "CBBH",
        "EM",
        {
            "CBBH": "CBBH",
            "CBNL": "CBNL",
            "CBL": "CBNL",
        },
        True,
    ),
    # ('BULL', 'NW', {}, False),
    ("SELT", "NW", {}, True),  # Selwyns
    ("ROSS", "Y", {}, False),  # Ross Travel Ticketer
    ("GRYC", "EM", {}, False),
    ("CKMR", "SE", {}, False),
    # ('A2BR', 'EA',  {}, False),
    ("A2BV", "NW", {}, False),
    # ('STNE', 'NE',  {
    #     'STNE': 'STNE',
    #     'STNT': 'STNT',
    # }, False),
    ("LAWS", "EM", {}, False),
    # ('BMCS', 'SE',  {}, False),
    ("AJCO", "EA", {}, False),
    ("LTEA", "EA", {}, False),
    ("CPLT", "EA", {}, False),
    (
        "OBUS",
        "EA",
        {
            "OURH": "OURH",
            "OBUS": "OBUS",
        },
        False,
    ),
    ("PLNG", "EA", {}, False),
    ("SNDR", "EA", {}, False),
    ("AWAY", "EA", {}, False),
    ("LYNX", "EA", {}, False),
    ("IPSW", "EA", {}, False),
    ("WNCT", "EA", {}, False),
    ("WHIP", "EA", {}, False),
    ("SIMO", "EA", {}, False),
    ("BEES", "EA", {}, False),
    ("HACO", "EA", {}, False),
    ("DEWS", "EA", {}, False),
    # Rotala Group of Companies
    (
        "WNGS",
        None,
        {
            "WINGS": "WNGS",
            "TGM": "WNGS",  # Diamond SE
            "NXHH": "NXHH",  # Hotel Hoppa
            "DIAM": "DIAM",  # Diamond WM
            "GTRI": "GTRI",  # Diamond NW
            "PBLT": "PBLT",  # Preston
        },
        False,
    ),
    (
        "Viking Coaches",
        "NW",
        {"VIKG": "VIKG"},
        False,
    ),  # Viking (BODS API thinks their operator code is WVIK, but that's a different Viking)
    ("ALSC", "NW", {}, False),  # Happy Al's
    ("LCAC", "NW", {}, False),
    ("LNNE", "NW", {}, False),
    ("NUTT", "NW", {}, False),
    ("BLAC", "NW", {}, False),
    ("STOT", "NW", {}, False),
    ("IRVD", "NW", {}, False),
    ("ROOS", "SW", {}, False),
    ("SEWR", "SW", {}, False),
    ("LUCK", "SW", {}, False),
    ("GVTR", "NE", {}, False),
    ("COTY", "NE", {}, False),
    ("SBBC", "NE", {}, True),
    ("LMST", "WM", {}, False),
    ("TEXP", "WM", {}, False),
    ("BANG", "WM", {}, False),
    ("SLVL", "WM", {}, False),
    ("ENSB", "SE", {}, True),
    ("AWAN", "SE", {}, False),
    ("HRBT", "SE", {}, False),
    ("CARL", "SE", {}, False),
    ("FALC", "SE", {}, False),
    ("VECT", "SE", {}, True),
    ("ACME", "SE", {}, False),
    # ('LTKR', 'SE', {}, False),
    ("BRYL", "EM", {}, False),
    ("MDCL", "EM", {}, False),
    (
        "Notts & Derby",
        "EM",
        {  # they don't have a NOC assigned on BODS, so can't be searched for using the API
            "NDTR": "NDTR"
        },
        True,
    ),
    ("COMM", "EM", {}, False),
    ("RELD", "Y", {}, False),
    ("SSSN", "Y", {}, False),
    ("KJTR", "Y", {}, False),
    (
        "HCTY",
        "Y",
        {
            "HCTY": "HCTY",  # Connexions
            "YRRB": "YRRB",  # 'Road Runner'
        },
        False,
    ),
    ("KENS", "Y", {}, False),
    (
        "NCTP",
        None,
        {
            "NCTP": "NCTP",  # CT Plus Bristol (/London)
            "POWB": "POWB",  # Powells
            "CTPL": "CTPL",  # CT Plus Yorkshire
        },
        False,
    ),
    ("DELA", "EM", {}, False),
    ("SULV", "SE", {}, False),
    ("WBSV", "SE", {}, False),
    ("REDE", "SE", {}, False),
    ("GPLM", "SE", {}, False),
    ("CLNB", "SE", {}, False),
    ("RCHC", "SE", {}, True),
    ("CRSS", "WM", {}, True),  # NN Cresswell
    (
        "DAGC",
        None,
        {
            "DAGC": "DAGC",
            "CRDR": "CRDR",
        },
        False,
    ),
    # Go-Ahead
    (
        "Go East Anglia",
        "EA",
        {
            "KCTB": "KCTB",
            "HEDO": "HEDO",
            "CHAM": "CHAM",
        },
        False,
    ),
    (
        "Go South Coast",
        "SW",
        {
            "BLUS": "BLUS",
            "DAMY": "DAMY",
            "SWWD": "SWWD",
            "SVCT": "SVCT",
            "TDTR": "TDTR",
            "UNIL": "UNIL",
            "WDBC": "WDBC",
        },
        False,
    ),
    # ('Brighton and Hove Buses', 'SE', {
    #     'BHBC': 'BHBC',
    # }, False),
    (
        "Go North East",
        "NE",
        {
            "GNEL": "GNEL",
        },
        False,
    ),
    (
        "Go North West",
        "NW",
        {
            "GONW": "GONW",
        },
        False,
    ),
    (
        "Oxford Bus Company",
        "SE",
        {
            "OXBC": "OXBC",
            "CSLB": "CSLB",
            "THTR": "THTR",
            "CSSO": "CSSO",
        },
        False,
    ),
    # ('East Yorkshire', 'Y', {
    #     'EYMS': 'EYMS',
    # }, False),
    ("DRMC", "WM", {}, True),
    ("SARG", "WM", {}, False),
    (
        "AMBS",
        "EA",
        {
            "AMBS": "AMBS",
            "SEMM": "SEMM",
        },
        True,
    ),
    ("RDRT", "SE", {"RR": "RDRT", "RR1": "RDRT"}, False),
    # ('REDL', 'SE', {
    #     'REDL': 'RLNE',
    # }, False),
    ("GOGO", "NW", {}, False),
    ("HATT", "NW", {}, False),
    ("FCHS", "NW", {}, False),
    ("CUBU", "NW", {}, False),
    ("HUYT", "NW", {}, False),
    ("AJTX", "NW", {}, False),
    ("PPBU", "NW", {}, False),
    ("EAZI", "NW", {}, False),
    ("MAGH", "NW", {}, False),
    ("MAND", "SE", {}, False),
    # ('RLNE', 'SE', {}, False),
    ("SOUT", "SW", {}, False),
]

# Some operators' timetables are fetched directly from e.g.
# https://opendata.ticketer.com/uk/LYNX/routes_and_timetables/current.zip
# rather than via the Bus Open Data site,
# because sometimes BODS doesn't detect updates
TICKETER_OPERATORS = [
    # https://opendata.ticketer.com/uk/Ipswich_Buses/routes_and_timetables/current.zip
    ("EA", ["Ipswich_Buses", "IPSW"]),
    # URL happens to contain operator code -
    # https://opendata.ticketer.com/uk/BDRB/routes_and_timetables/current.zip
    ("EA", ["BDRB"], "BorderBus"),
    ("EA", ["LYNX"], "Lynx"),
    ("EA", ["WHIP"], "Whippet"),
    ("EA", ["AMBS"], "Ambassador Travel"),
    ("EA", ["WNCT"], "West Norfolk Community Transport"),
    ("EA", ["Simonds", "SIMO"]),
    ("EA", ["Beestons_(Hadleigh)_Ltd", "BEES"]),
    ("EM", ["Brylaine", "BRYL"]),
    ("EM", ["Midland_Classic", "MDCL"]),
    # ('EM', ['Notts_and_Derby', 'NDTR']),
    ("EM", ["DELA"], "Delaine Buses"),
    ("NE", ["A-Line_Coaches_Tyne_&_Wear", "ALGC"]),
    ("NE", ["Coatham_Coaches", "COTY"]),
    ("NW", ["STOT"], "Stotts Tours"),
    ("NW", ["D&G_Bus_Ltd", "DAGC", "CRDR"]),
    ("NW", ["Finches", "FCHS"]),
    ("NW", ["GOGO"], "Go Goodwins"),
    ("NW", ["BEVC"], "Belle Vue"),
    ("SE", ["WBSV"], "White Bus"),
    ("SE", ["REDE"], "Red Eagle"),
    ("SE", ["GPLM"], "Grant Palmer"),
    ("SE", ["CLNB"], "Carlone Buses"),
    # ('SE', ['RCHC'], 'Richmonds Coaches'),
    ("SE", ["Vectare", "VECT"]),
    ("SE", ["FALC"], "Falcon Buses"),
    ("SE", ["Sullivan_Buses", "SULV"]),
    ("SE", ["ENSB"], "Ensignbus"),
    # ('SE', ['RRTR'], 'Red Rose Travel'),
    ("SE", ["Redline_Buses_Ltd", "REDL"]),
    ("SE", ["Compass_Travel", "COMT"]),
    ("SW", ["NTCP", "NCTP"], "HCT Group"),
    ("WM", ["Travel_Express", "TEXP"]),
    ("WM", ["Banga_Buses", "BANG"]),
    ("WM", ["Silverline_LandFlight_Limited", "SLVL"]),
    ("WM", ["LMST"], "LMS Travel"),
    ("Y", ["Shoreline_Suncruisers", "SSSN"]),
    ("Y", ["POWB", "CTPL"], "HCT Group"),
    ("Y", ["RELD"], "Reliance Motor Services"),
    ("Y", ["HCTY"], "Connexions Buses"),
    ("Y", ["KJTR"], "York Pullman"),
    # Arriva Operators
    ("W", ["ACYM"], "Arriva Cymru"),
    ("NW", ["AMAN", "ANWE"], "Arriva North West"),
    ("NW", ["AMSY"], "Arriva Merseyside"),
    ("NE", ["ARDU", "ANEA"], "Arriva Durham"),
    ("NE", ["ANUM"], "Arriva Northumbria"),
    ("Y", ["WRAY", "YTIG"], "Arriva Yorkshire"),
    ("WM", ["AMNO"], "Arriva Midlands North"),
    ("EM", ["AMID", "AFCL", "ADER"], "Arriva Midlands"),
    ("SE", ["ARBB", "ASES", "GLAR"], "Arriva Beds & Bucks"),
    ("SE", ["AMTM", "ARHE"], "Arriva Kent Thameside"),
    ("SE", ["AKSS", "AMTM"], "Arriva Kent & Surrey"),
    # Go-Ahead Operators
    ("SW", ["PLYC", "TFCN"], "Go South West"),
    # ('SE', ['METR'], 'Metrobus'),
    ("SE", ["OXBC", "CSLB", "THTR"], "Oxford Bus Company"),
    ("NW", ["GONW"], "Go North West"),
    ("NE", ["GNEL"], "Go North East"),
    # ('Y', ['EYMS'], 'East Yorkshire'),
    ("EA", ["GOEA", "KCTB", "HEDO", "CHAM"], "Go East Anglia"),
    # Rotala Operators
    ("WM", ["DIAM"], "Diamond Bus"),
    ("NW", ["GTRI"], "Diamond Bus North West"),
    ("NW", ["PBLT"], "Preston Bus"),
    ("SE", ["WNGS"], "Diamond South East"),
]
