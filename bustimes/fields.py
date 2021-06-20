from datetime import timedelta
from django.utils.dateparse import parse_duration
from django.db.models.fields import DurationField


class SecondsField(DurationField):
    """We need to support more than 24 hours
    (for bus journeys that span midnight),
    so a TimeField won't suffice,
    but a DurationField is too precise
    (and uses too much space).
    This is a happy medium.
    """
    @staticmethod
    def get_internal_type():
        return "IntegerField"

    @staticmethod
    def get_db_converters(connection):
        return [SecondsField.convert]

    @staticmethod
    def get_db_prep_value(value, connection, prepared=False):
        if value is None:
            return value
        if isinstance(value, str):
            value = parse_duration(value)
        return int(value.total_seconds())

    @staticmethod
    def convert(value, _expression, _connection, _context=None):
        if value is None:
            return value
        return timedelta(seconds=value)
