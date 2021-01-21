"""These settings rely on various environment variables being set
"""

import os
import sys
from aioredis import ReplyError
from autobahn.exception import Disconnected


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split()

TEST = 'test' in sys.argv or 'pytest' in sys.argv[0]
DEBUG = bool(os.environ.get('DEBUG', False)) or TEST

SERVER_EMAIL = 'contact@bustimes.org'
DEFAULT_FROM_EMAIL = 'bustimes.org <contact@bustimes.org>'

if TEST:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
else:
    EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True
    EMAIL_TIMEOUT = 10

INSTALLED_APPS = [
    'accounts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.sitemaps',
    'busstops',
    'bustimes',
    'disruptions',
    'fares',
    'vehicles',
    'vosa',
    'antispam',
    'email_obfuscator',
    'channels',
    'api',
    'rest_framework',
    'django_filters'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'busstops.middleware.real_ip_middleware',
    'busstops.middleware.not_found_redirect_middleware',
]

SECURE_REFERRER_POLICY = None

if DEBUG and 'runserver' in sys.argv:
    INTERNAL_IPS = ['127.0.0.1']
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
        'debug_toolbar_force.middleware.ForceDebugToolbarMiddleware',
    ]

ROOT_URLCONF = 'buses.urls'

ASGI_APPLICATION = 'vehicles.routing.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME', 'bustimes'),
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'OPTIONS': {
            'application_name': os.environ.get('APPLICATION_NAME') or ' '.join(sys.argv)[:63],
            'connect_timeout': 3
        },
        'TEST': {
            'SERIALIZE': False
        }
    }
}
if TEST:
    TEST_RUNNER = 'django_slowtests.testrunner.DiscoverSlowestTestsRunner'
    NUM_SLOW_TESTS = 20

AUTH_USER_MODEL = 'accounts.User'
LOGIN_REDIRECT_URL = '/vehicles'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100
}

if os.environ.get('READ_ONLY_DB_HOST'):
    REPLICA_DATABASES = []
    for i, host in enumerate(os.environ['READ_ONLY_DB_HOST'].split()):
        key = f'read-only-{i}'
        DATABASES[key] = DATABASES['default'].copy()
        DATABASES[key]['HOST'] = host
        REPLICA_DATABASES.append(key)
    DATABASE_ROUTERS = ['multidb.PinningReplicaRouter']
    MIDDLEWARE.append('busstops.middleware.pin_db_middleware')
    READ_DATABASE = key
else:
    READ_DATABASE = 'default'

DATA_UPLOAD_MAX_MEMORY_SIZE = None
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

CHANNEL_LAYERS = {
    'default': {}
}
if TEST:
    CHANNEL_LAYERS['default'] = {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
else:
    CHANNEL_LAYERS['default'] = {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [CELERY_BROKER_URL],
            'expiry': 20
        }
    }


STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(BASE_DIR, '..', 'bustimes-static'))
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

TEMPLATE_MINIFER_STRIP_FUNCTION = 'buses.utils.minify'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        }
    }
]
if DEBUG:
    TEMPLATES[0]['OPTIONS']['loaders'] = ['django.template.loaders.app_directories.Loader']
else:
    TEMPLATES[0]['OPTIONS']['loaders'] = [('django.template.loaders.cached.Loader', [
        # 'django.template.loaders.app_directories.Loader'
        'template_minifier.template.loaders.app_directories.Loader'
    ])]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache'
    } if TEST else {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': os.environ.get('MEMCACHED_LOCATION', '127.0.0.1:11211')
    }
}

VARNISH_HOST = os.environ.get('VARNISH_HOST')
VARNISH_PORT = os.environ.get('VARNISH_PORT')
if VARNISH_HOST and VARNISH_PORT:
    VARNISH = (VARNISH_HOST, int(VARNISH_PORT))
else:
    VARNISH = None

TIME_FORMAT = 'H:i'
DATE_FORMAT = 'l j F Y'
DATETIME_FORMAT = 'j M H:i'
TIME_ZONE = 'Europe/London'
USE_TZ = True
USE_I18N = False


def before_send(event, hint):
    if 'exc_info' in hint:
        exc_type, exc_value, traceback = hint['exc_info']
        if isinstance(exc_value, ReplyError) or isinstance(exc_value, Disconnected):
            return
    return event


if TEST:
    pass
elif not DEBUG and 'collectstatic' not in sys.argv and 'SENTRY_DSN' in os.environ:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=os.environ['SENTRY_DSN'],
        integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
        ignore_errors=[KeyboardInterrupt],
        before_send=before_send
    )
else:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    }

TFL = {
    'app_id': os.environ.get('TFL_APP_ID'),
    'app_key': os.environ.get('TFL_APP_KEY')
}
TFWM = {
    'app_id': os.environ.get('TFWM_APP_ID'),
    'app_key': os.environ.get('TFWM_APP_KEY')
}

DATA_DIR = os.path.join(BASE_DIR, 'data')
TNDS_DIR = os.path.join(DATA_DIR, 'TNDS')

AKISMET_API_KEY = os.environ.get('AKISMET_API_KEY')
AKISMET_SITE_URL = 'https://bustimes.org'

IE_COLLECTIONS = (
    'goahead', 'luasbus', 'dublinbus', 'kenneallys', 'locallink', 'irishrail', 'ferries',
    'manda', 'finnegans', 'citylink', 'nitelink', 'buseireann', 'mcgeehan',
    'mkilbride', 'expressbus', 'edmoore', 'collins', 'luas', 'sro',
    'dublincoach', 'burkes', 'mhealy', 'kearns', 'josfoley', 'buggy',
    'jjkavanagh', 'citydirect', 'aircoach', 'matthews', 'wexfordbus',
    'dualway', 'tralee', 'sbloom', 'mcginley', 'swordsexpress', 'suirway',
    'sdoherty', 'pjmartley', 'mortons', 'mgray', 'mcgrath', 'mangan',
    'lallycoach', 'halpenny', 'eurobus', 'donnellys', 'cmadigan', 'bkavanagh',
    'ptkkenneally', 'farragher', 'fedateoranta', 'ashbourneconnect'
)
PASSENGER_OPERATORS = [
    ('Nottingham City Transport', 'https://www.nctx.co.uk/open-data', 'EM', {
        'NCT': 'NCTR'
    }),
    ('Borders Buses', 'https://www.bordersbuses.co.uk/open-data', 'S', {
        'BB': 'BORD',
    }),
    ('morebus', 'https://www.morebus.co.uk/open-data', 'SW', {
        'SQ': 'WDBC',
        'DAM': 'DAMY',
        'BLU': 'BLUS',
    }),
    ('UNIBUS', 'https://www.unibuses.co.uk/open-data', 'SW', {
        'SQ': 'WDBC',
    }),
    ('Bluestar', 'https://www.bluestarbus.co.uk/open-data', 'SW', {
        'SQ': 'BLUS',
        'UNIL': 'UNIL',
    }),
    ('Unilink', 'https://www.unilinkbus.co.uk/open-data', 'SW', {
        'SQ': 'UNIL',
        'BLUS': 'BLUS',
    }),
    ('Salisbury Reds', 'https://www.salisburyreds.co.uk/open-data', 'SW', {
        'SQ': 'SWWD',
        'DAM': 'DAMY',
    }),
    ('Southern Vectis', 'https://www.islandbuses.info/open-data', 'SW', {
        'SQ': 'SVCT',
        'DAM': 'DAMY',
    }),
    ('Reading Buses', 'https://www.reading-buses.co.uk/open-data', 'SE', {
        'RB': 'RBUS',
        'GLRB': 'GLRB',  # Green Line
    }),
    ('Courtney Buses', 'https://www.courtneybuses.com/open-data', 'SE', {
        'CTNY': 'CTNY',
        'RB': 'RBUS',
        'THVB': 'THVB'
    }),
    ('West Coast Motors', 'https://www.westcoastmotors.co.uk/open-data', 'S', {
        'WCM': 'WCMO',
        'GCB': 'GCTB',  # Glasgow Citybus
    }),
    ('Cardiff Bus', 'https://www.cardiffbus.com/open-data', 'W', {
        'CB': 'CBUS',
        # 'NB': '',
    }),
    ('Yellow Buses', 'https://www.yellowbuses.co.uk/open-data', 'SW', {
        'YELL': 'YELL',
    }),
    ('Swindon’s Bus Company', 'https://www.swindonbus.co.uk/open-data', 'SW', {
        'TT': 'TDTR',
        'SBCR': 'TDTR',  # rural
        'NATI': 'TDTR',  # Nationwide Building Society
    }),
    ('Brighton & Hove Buses', 'https://www.buses.co.uk/open-data', 'SE', {
        'BH': 'BHBC',
    }),
    ('East Yorkshire', 'https://www.eastyorkshirebuses.co.uk/open-data', 'Y', {
        'EY': 'EYMS',
    }),
    ('Blackpool Transport', 'https://www.blackpooltransport.com/open-data', 'NW', {
        'RR': 'BLAC',
    }),
    ('Transdev Blazefield', 'https://www.transdevbus.co.uk/open-data', 'NW', {
        'LUI': 'LNUD',
        'ROS': 'ROST',
        'BPT': 'BPTR',
        'KDT': 'KDTR',
        'HDT': 'HRGT',
        'YCD': 'YCST',
    }),
    ('Go North East', 'https://www.gonortheast.co.uk/open-data', 'NE', {
        'GNE': 'GNEL',
    }),
    ('McGill’s', 'https://data.discoverpassenger.com/operator/mcgills', 'S', {
        'MCG': 'MCGL',
        'McG': 'MCGL',
    }),
]
FIRST_OPERATORS = [
]
BOD_OPERATORS = [
    ('FECS', None, {
        'FYOR': 'FYOR',
        'FPOT': 'FPOT',
        'FSYO': 'FSYO',
        'FMAN': 'FMAN',
        'FLDS': 'FLDS',
        'FHUD': 'FHUD',
        'FSMR': 'FSMR',
        'FHAL': 'FHAL',
        'FBRA': 'FBRA',
        'FESX': 'FESX',
        'FECS': 'FECS',
        'FCWL': 'FCWL',
        'FHDO': 'FHDO',
        'FTVA': 'FTVA',
        'FHAM': 'FHAM',
        'FDOR': 'FDOR',
        'FBOS': 'FBOS',
        'FLEI': 'FLEI',
        'RRAR': 'RRAR',
        'FBRI': 'FBRI',
        'FWYO': 'FWYO',
    }, False),
    ('TNXB', 'WM', {
        'TNXB': 'TNXB',
        'TCVW': 'TCVW',
    }, False),
    ('UNOE', 'SE', {
        'UBN': 'UNOE',
        'UNIB': 'UNOE',
        'OP': 'UNOE',
        'UN': 'UNOE',
    }, False),
    ('TBTN', 'EM', {
        '574T': 'TBTN',
    }, False),
    ('KBUS', 'EM', {
        'KN': 'KBUS',
    }, False),
    ('GPLM', 'SE', {
        'OP': 'GPLM',
        'GP': 'GPLM'
    }, False),
    ('WHIP', 'EA', {
        'OP': 'WHIP'
    }, False),
    ('CSVC', 'EA', {
        'CS': 'CSVC'
    }, False),
    ('HIPK', 'EM', {
        'OP': 'HIPK',
        'HPB': 'HIPK',
    }, False),
    ('HNTS', 'EM', {}, False),
    # ('SLBS', 'WM', {}, True),
    ('DAGC', 'NW', {}, False),
    ('RLNE', 'SE', {}, True),
    ('GOGO', 'NW', {}, False),
    ('BRYL', 'EM', {}, False),
    ('LODG', 'SE', {}, False),
    ('BDRB', 'EA', {}, False),
    ('SIMO', 'EA', {}, False),
    ('SULV', 'SE', {
        'SN': 'SULV'
    }, False),
    ('FRDS', 'SE', {}, False),
    ('BEES', 'EA', {}, False),
    ('COTY', 'NE', {}, False),

    ('AVMT', 'SW', {}, False),
    ('BZCO', 'SW', {}, False),
    ('C2WI', 'SW', {}, False),
    ('CNTY', 'SW', {}, False),
    ('COAC', 'SW', {}, False),
    ('COTS', 'SW', {}, False),
    ('CRYC', 'SW', {}, False),
    ('DTCO', 'SW', {}, False),
    ('FRMN', 'SW', {}, False),
    ('FSRV', 'SW', {}, False),
    ('FTZL', 'SW', {}, False),
    ('GWIL', 'SW', {}, False),
    ('HGCO', 'SW', {}, False),
    ('HOPE', 'SW', {}, False),
    ('JACK', 'SW', {}, False),
    ('LTRV', 'SW', {}, False),
    ('NAKL', 'SW', {}, False),
    ('OTSS', 'SW', {}, False),
    ('PULH', 'SW', {}, False),
    ('RIDL', 'SW', {}, False),
    ('RSLN', 'SW', {}, False),
    ('SMST', 'SW', {}, False),
    ('SWCO', 'SW', {}, False),
    ('TAWT', 'SW', {}, False),
    ('TLYH', 'SW', {}, False),
    ('TOTN', 'SW', {}, False),
    ('YEOS', 'SW', {}, False),

    ('RDRT', 'SE', {
        'RR': 'RDRT',
        'RR1': 'RDRT'
    }, False),
]
STAGECOACH_OPERATORS = [
    ('S', 'sblb', 'Stagecoach Bluebird', {'SBLB': 'SBLB'}),
    ('S', 'scfi', 'Stagecoach East Scotland', {
        'SCPE': 'SCPE',
        'SSPH': 'SSPH',  # (code not used in data)
        'STSY': 'STSY',
        'SSTY': 'SSTY',  # (code not used in data)
        'SCFI': 'SCFI',
    }),
    ('S', 'schi', 'Stagecoach Highlands', {
        'SCHI': 'SCHI',
        'SCOR': 'SCOR',
        'SINV': 'SINV',  # (code not used in data)
    }),
    ('NE', 'scne', 'Stagecoach North East', {
        'SCNE': 'SCNE',
        'SCSS': 'SCSS',
        'SCSU': 'SCSU',
        'SCTE': 'SCTE',
        'SCHA': 'SCHA'
    }),
    ('S', 'stws', 'Stagecoach West Scotland', {
        'SCGS': 'SCGS',
        'STGS': 'STGS',  # (code not used in data)
        'STWS': 'STWS'
    }),
    ('EM', 'scem', 'Stagecoach East Midlands', {
        'SCGH': 'SCGH',
        'SCGR': 'SCGR',  # (code not used in data)
        'SCLI': 'SCLI',
        'NFKG': 'NFKG'
    }),
    ('SE', 'scso', 'Stagecoach South', {
        'SCPY': 'SCPY',
        'SCHM': 'SCHM',
        'SCHW': 'SCHW',  # (code not used in data)
        'SCCO': 'SCCO',
        'SMSO': 'SMSO',  # (code not used in data)
    }),
    ('SE', 'scek', 'Stagecoach South East', {
        'SCEK': 'SCEK',
        'SCEB': 'SCEB',
        'SCHT': 'SCHT'
    }),
    ('Y', 'syrk', 'Stagecoach Yorkshire', {
        'SYRK': 'SYRK',
        'YSYC': 'YSYC',
        'CLTL': 'CLTL',  # (code not used in data)
    }),
    ('NW', 'sccu', 'Stagecoach Cumbria', {
        # 'ANEA': 'ANEA',
        'SCMB': 'SCMB',
        'SCCU': 'SCCU',  # (code not used in data)
    }),
    ('NW', 'scmn', 'Stagecoach Manchester', {
        'SCMN': 'SCMN',
        'SWIG': 'SWIG'
    }),
    ('NW', 'scmy', 'Stagecoach Merseyside', {
        'SCMY': 'SCMY'
    }),
    ('SW', 'sdvn', 'Stagecoach South West', {'SDVN': 'SDVN'}),
    ('SE', 'sccm', 'Stagecoach East', {
        'SCBD': 'SCBD',
        'SCCM': 'SCCM',
        'SCPB': 'SCPB',
        'SCHU': 'SCHU'
    }),
    ('EM', 'scnh', 'Stagecoach Midlands', {
        'SCNH': 'SCNH',
        'SCWW': 'SCWW'
    }),
    ('SE', 'scox', 'Stagecoach Oxfordshire', {'SCOX': 'SCOX'}),
    ('SW', 'scgl', 'Stagecoach West', {
        'SSWN': 'SSWN',
        'SCGL': 'SCGL'
    }),
    ('W', 'sswl', 'Stagecoach South Wales', {'SSWL': 'SSWL'}),
    ('Y', 'tram', 'Stagecoach Supertram', {'SCST': 'SCST'}),
]
TICKETER_OPERATORS = [
    ('NW', ['WBTR'], 'Warrington’s Own Buses'),
    ('EA', ['LYNX'], 'Lynx'),
    ('EA', ['Ipswich_Buses', 'IPSW'], 'Ipswich Buses'),
    ('EM', ['Notts_and_Derby', 'NDTR'], 'Notts and Derby'),
    ('Y', ['RELD'], 'Reliance Motor Services'),
    ('EA', ['GOEA', 'KCTB', 'HEDO', 'CHAM'], 'Go East Anglia'),
    ('SW', ['PLYC', 'TFCN'], 'Go South West'),
    ('SE', ['METR'], 'Metrobus'),
    ('SE', ['OXBC', 'CSLB', 'THTR'], 'Oxford Bus Company'),
    # ('NW', ['GONW'], 'Go North West'),
    ('W', ['ACYM'], 'Arriva Cymru'),
    ('NW', ['AMAN', 'ANWE'], 'Arriva North West'),
    ('NW', ['AMSY'], 'Arriva Merseyside'),
    ('NE', ['ARDU', 'ANEA'], 'Arriva Durham'),
    ('NE', ['ANUM'], 'Arriva Northumbria'),
    ('Y', ['WRAY'], 'Arriva Yorkshire'),
    ('Y', ['YTIG'], 'Yorkshire Tiger'),
    ('WM', ['AMNO'], 'Arriva Midlands North'),
    ('EM', ['AMID', 'AFCL'], 'Arriva Midlands'),
    ('SE', ['ARBB', 'ASES', 'GLAR'], 'Arriva Beds & Bucks'),
    ('SE', ['AMTM', 'ARHE'], 'Arriva Thameside'),
    ('SE', ['AKSS'], 'Arriva Kent & Surrey'),
    ('EM', ['NOCT'], 'CT4N'),
    ('WM', ['DIAM'], 'Diamond Bus'),
    ('NW', ['GTRI'], 'Diamond Bus North West'),
    ('NW', ['PBLT'], 'Preston Bus'),
    # ('SE', ['WNGS', 'NXHH'], 'Hallmark Connections'),
    ('WM', ['LMST'], 'LMS Travel'),
    ('SE', ['ENSB'], 'Ensignbus'),
    ('EA', ['AMBS'], 'Ambassador Travel'),
]
