"""These settings rely on various environment variables being set
"""

import os
import sys
import raven


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'bustimes.org.uk\n127.0.0.1\nlocalhost').split()

DEBUG = bool(os.environ.get('DEBUG', False))

SERVER_EMAIL = 'contact@bustimes.org.uk'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'haystack',
    'busstops',
    'pipeline',
    'email_obfuscator',
    'raven.contrib.django.raven_compat'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'busstops.middleware.not_found_redirect_middleware',
]

if DEBUG and 'runserver' in sys.argv and not bool(os.environ.get('TRAVIS')):
    INTERNAL_IPS = ['127.0.0.1']
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.append('debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'buses.urls'

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    } if DEBUG else {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'haystack',
        'INCLUDE_SPELLING': True,
    },
}
HAYSTACK_IDENTIFIER_METHOD = 'buses.utils.get_identifier'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASS'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'NAME': os.environ.get('DB_NAME', 'bustimes'),
        'PORT': os.environ.get('DB_PORT')
    }
}

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', os.path.join(BASE_DIR, '..', 'bustimes-static'))
if DEBUG:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineStorage'
else:
    STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
)
PIPELINE = {
    'COMPILERS': [
        'pipeline.compilers.sass.SASSCompiler',
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
        },
        'departures': {
            'source_filenames': (
                'js/bower_components/reqwest/reqwest.min.js',
                'js/departures.js',
            ),
            'output_filename': 'js/departures.min.js',
        },
        'map': {
            'source_filenames': (
                'js/bower_components/leaflet/dist/leaflet.js',
                'js/map.js',
            ),
            'output_filename': 'js/map.min.js',
        },
    },
    'YUGLIFY_BINARY': './node_modules/.bin/yuglify',
    'CSS_COMPRESSOR': None,
    'SASS_ARGUMENTS': '--style compressed --trace',
}

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
                'busstops.context_processors.amp',
                'busstops.context_processors.random',
            )
        }
    }
]

TIME_FORMAT = 'H:i'
DATE_FORMAT = 'j F Y'
TIME_ZONE = 'Europe/London'
USE_I18N = False

STREETVIEW_KEY = os.environ.get('STREETVIEW_KEY')
STREETVIEW_SECRET = os.environ.get('STREETVIEW_SECRET')

TRANSPORTAPI_APP_ID = os.environ.get('TRANSPORTAPI_APP_ID')
TRANSPORTAPI_APP_KEY = os.environ.get('TRANSPORTAPI_APP_KEY')

TNDS_DIR = os.path.join(BASE_DIR, 'data', 'TNDS')

RAVEN_CONFIG = {
    'dsn': os.environ.get('SENTRY_DSN'),
    'release': raven.fetch_git_sha(BASE_DIR)
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'
    } if DEBUG else {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'LOCATION': '127.0.0.1:11211'
    }
}
