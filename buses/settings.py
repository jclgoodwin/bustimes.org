"""These settings rely on various environment variables being set
"""

import os
import sys
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split()

DEBUG = bool(os.environ.get('DEBUG', False)) or 'test' in sys.argv

SERVER_EMAIL = 'contact@bustimes.org'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.sitemaps',
    'haystack',
    'busstops',
    'bustimes',
    'vehicles',
    'vosa',
    'pipeline',
    'antispam',
    'email_obfuscator',
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

if DEBUG and 'runserver' in sys.argv:
    INTERNAL_IPS = ['127.0.0.1']
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
        'debug_toolbar_force.middleware.ForceDebugToolbarMiddleware',
    ]

ROOT_URLCONF = 'buses.urls'

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    } if DEBUG else {
        'ENGINE': 'haystack.backends.elasticsearch2_backend.Elasticsearch2SearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'haystack',
        'INCLUDE_SPELLING': True,
    },
}
HAYSTACK_IDENTIFIER_METHOD = 'buses.utils.get_identifier'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME', 'bustimes'),
        'DISABLE_SERVER_SIDE_CURSORS': True,
        'OPTIONS': {
            'application_name': os.environ.get('APPLICATION_NAME', ' '.join(sys.argv))
        }
    }
}

if os.environ.get('READ_ONLY_DB_HOST'):
    REPLICA_DATABASES = []
    for i, host in enumerate(os.environ['READ_ONLY_DB_HOST'].split()):
        key = f'read-only-{i}'
        DATABASES[key] = DATABASES['default'].copy()
        DATABASES[key]['HOST'] = host
        REPLICA_DATABASES.append(key)
    DATABASE_ROUTERS = ['multidb.PinningReplicaRouter']
    MIDDLEWARE.append('busstops.middleware.admin_db_middleware')

DATA_UPLOAD_MAX_MEMORY_SIZE = None
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379')

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(BASE_DIR, '..', 'bustimes-static'))
MEDIA_URL = '/media/'
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', os.path.join(BASE_DIR, '..', 'bustimes-media'))

if DEBUG:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'
else:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
)
PIPELINE = {
    'COMPILERS': [
        'busstops.compilers.AutoprefixerSASSCompiler',
    ],
    'STYLESHEETS': {
        'main': {
            'source_filenames': (
                'css/style.scss',
            ),
            'output_filename': 'css/style.css',
        },
        'ie': {
            'source_filenames': (
                'css/ie.scss',
            ),
            'output_filename': 'css/ie.css',
        }
    },
    'JAVASCRIPT': {
        'frontpage': {
            'source_filenames': (
                'js/frontpage.js',
            ),
            'output_filename': 'js/frontpage.min.js',
            'extra_context': {
                'async': True
            }
        },
        'global': {
            'source_filenames': (
                'js/global.js',
            ),
            'output_filename': 'js/global.min.js',
            'extra_context': {
                'async': True
            }
        },
        'timetable': {
            'source_filenames': (
                'js/timetable.js',
            ),
            'output_filename': 'js/timetable.min.js',
            'extra_context': {
                'async': True
            }
        },
        'bigmap': {
            'source_filenames': (
                'js/reqwest.min.js',
                'js/bigmap.js',
            ),
            'output_filename': 'js/bigmap.min.js',
            'extra_context': {
                'async': not DEBUG
            }
        },
        'servicemap': {
            'source_filenames': (
                'js/loadjs/loadjs.min.js',
                'js/reqwest.min.js',
                'js/servicemap.js',
            ),
            'output_filename': 'js/servicemap.min.js',
            'extra_context': {
                'async': not DEBUG
            }
        },

    },
    'YUGLIFY_BINARY': os.path.join(BASE_DIR, 'node_modules', '.bin', 'yuglify'),
    'CSS_COMPRESSOR': None,
    'SASS_BINARY': os.path.join(BASE_DIR, 'node_modules', '.bin', 'sass'),
    'SASS_ARGUMENTS': '--style compressed',
}
PIPELINE_AUTOPREFIXER_BINARY = os.path.join(BASE_DIR, 'node_modules', '.bin', 'postcss')

TEMPLATE_MINIFER_STRIP_FUNCTION = 'buses.utils.minify'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'debug': DEBUG,
            'loaders': (
                'django.template.loaders.app_directories.Loader' if DEBUG else (
                    'django.template.loaders.cached.Loader', (
                        'template_minifier.template.loaders.app_directories.Loader',
                    )
                ),
            ),
            'context_processors': (
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            )
        }
    }
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache'
    } if 'test' in sys.argv else {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': os.environ.get('MEMCACHED_LOCATION', '127.0.0.1:11211')
    }
}

TIME_FORMAT = 'H:i'
DATE_FORMAT = 'l j F Y'
DATETIME_FORMAT = 'j M H:i'
TIME_ZONE = 'Europe/London'
USE_TZ = True
USE_I18N = False

if not DEBUG and 'test' not in sys.argv and 'collectstatic' not in sys.argv:
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()]
    )

     MIDDLEWARE.append('beeline.middleware.django.HoneyMiddleware')

TRANSPORTAPI = {
   'app_id': os.environ.get('TRANSPORTAPI_APP_ID'),
   'app_key': os.environ.get('TRANSPORTAPI_APP_KEY')
}
TFL = {
    'app_id': os.environ.get('TFL_APP_ID'),
    'app_key': os.environ.get('TFL_APP_KEY')
}
TFWM = {
    'app_id': os.environ.get('TFWM_APP_ID'),
    'app_key': os.environ.get('TFWM_APP_KEY')
}
THEBUS_KEY = os.environ.get('THEBUS_KEY')

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
PASSENGER_OPERATORS = (
    # ('Nottingham City Transport', 'https://www.nctx.co.uk/open-data', 'EM', {
    #     'NCT': 'NCTR'
    # }),
    ('Borders Buses', 'https://www.bordersbuses.co.uk/open-data', 'S', {
        'BB': 'BORD',
    }),
    ('morebus', 'https://www.morebus.co.uk/open-data', 'SW', {
        'SQ': 'WDBC',
        'DAM': 'DAMY',
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
        'GLRB': 'GLRB',
    }),
    ('Courtney Buses', 'https://www.courtneybuses.com/open-data', 'SE', {
        'CTNY': 'CTNY',
    }),
    ('West Coast Motors', 'https://www.westcoastmotors.co.uk/open-data', 'S', {
        'WCM': 'WCMO',
        'GCB': 'GCTB',
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
    }),
    # ('Brighton & Hove Buses', 'https://www.buses.co.uk/open-data', 'SE', {
    #     'BH': 'BHBC',
    # }),
    # ('East Yorkshire', 'https://www.eastyorkshirebuses.co.uk/open-data', 'Y', {
    #     'EY': 'EYMS',
    # }),
    ('Blackpool Transport', 'https://www.blackpooltransport.com/open-data', 'NW', {
        'RR': 'BLAC',
    }),
)
