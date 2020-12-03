from vehicles.models import Channel


class Router:
    @staticmethod
    def db_for_read(model, **hints):
        if model is Channel:
            return 'read-only-0'
