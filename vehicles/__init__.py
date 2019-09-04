from .celery import app as celery_app


default_app_config = 'vehicles.apps.VehiclesConfig'


__all__ = ('celery_app',)
