import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'swzzL)M&ZkW(dmPtQXr4XaBSe@7cYguG@NPH@iRQo6c2h'

INSTALLED_APPS = (
    'busstops',
)

ROOT_URLCONF = 'busstops.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'USER': 'postgres',
        'HOST': 'localhost'
    }
}
