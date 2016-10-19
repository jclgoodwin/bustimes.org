"""These settings rely on various environment variables being set
"""

import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'bustimes.org.uk\n127.0.0.1\nlocalhost').split()

DEBUG = bool(os.environ.get('DEBUG', False))

SERVER_EMAIL = 'contact@bustimes.org.uk'
ADMINS = MANAGERS = (('Josh', 'contact@bustimes.org.uk'),)

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
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'busstops.middleware.not_found_redirect_middleware',
]

if DEBUG and 'test' not in sys.argv and not bool(os.environ.get('TRAVIS')):
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE_CLASSES = MIDDLEWARE[:-1] + ['debug_toolbar.middleware.DebugToolbarMiddleware']
    del MIDDLEWARE
    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.logging.LoggingPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'debug_toolbar.panels.profiling.ProfilingPanel'
    ]

ROOT_URLCONF = 'buses.urls'

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    } if DEBUG else {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': 'http://127.0.0.1:9200/',
        'INDEX_NAME': 'haystack',
    },
}
HAYSTACK_IDENTIFIER_METHOD = 'buses.utils.get_identifier'
#  HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

if not DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
            'LOCATION': '127.0.0.1:11211',
        }
    }

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'USER': os.environ.get('DATABASE_USER'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'NAME': os.environ.get('DATABASE_NAME', 'bustimes'),
    },
}

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

STATIC_URL = '/static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', '/home/josh/bustimes-static/')
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
            )
        }
    }
]

TIME_FORMAT = 'H:i'
DATE_FORMAT = 'j F Y'
TIME_ZONE = 'Europe/London'
USE_I18N = False

TRANSPORTAPI_APP_ID = os.environ.get('TRANSPORTAPI_APP_ID')
TRANSPORTAPI_APP_KEY = os.environ.get('TRANSPORTAPI_APP_KEY')
