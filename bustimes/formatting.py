import datetime
from django.utils.timezone import make_aware


def format_timedelta(duration):
    if duration is not None:
        duration = duration.total_seconds()
        hours = int(duration / 3600)
        while hours >= 24:
            hours -= 24
        minutes = int(duration % 3600 / 60)
        duration = f"{hours:0>2}:{minutes:0>2}"
        return duration


def time_datetime(time, date):
    seconds = time.total_seconds()
    while seconds >= 86400:
        date += datetime.timedelta(1)
        seconds -= 86400
    time = datetime.time(
        int(seconds / 3600), int(seconds % 3600 / 60), int(seconds % 60)
    )
    combined = datetime.datetime.combine(date, time)
    return make_aware(combined)
