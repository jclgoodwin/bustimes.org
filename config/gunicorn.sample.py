"""This is the Gunicorn configuration file. Copy it to gunicorn.py.

Environment variables need to be set here (see raw_env below) in order for
Django to work at all (in the case of SECRET_KEY), and for various external
services (Sentry, Google Maps, and Transport API) to work properly.
"""

bind = "127.0.0.1:8080"
workers = 5
raw_env = [
    "DB_USER=bustimes",
    "DB_PASS=",
    "SECRET_KEY=",
    "SENTRY_DSN=",
    "TRANSPORTAPI_APP_ID=",
    "TRANSPORTAPI_APP_KEY=",
]
