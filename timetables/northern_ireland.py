# import json
# import ciso8601
from datetime import date, timedelta


class Grouping(object):
    def __init__(self):
        self.name = ''
        self.rows = []

    def has_minor_stops(self):
        for row in self.rows:
            if row.part.timingstatus == 'OTH':
                return True

    def __str__(self):
        return self.name


class Timetable(object):
    def __init__(self):
        self.groupings = []

    def date_options(self):
        start_date = min(self.date, date.today())
        end_date = start_date + timedelta(weeks=2)
        while start_date <= end_date:
            yield start_date
            start_date += timedelta(days=1)
        if self.date >= start_date:
            yield self.date


class Part(object):
    def __init__(self, atco_code):
        self.stop = Stop(atco_code)


class Stop(object):
    def __init__(self, atco_code):
        self.atco_code = atco_code

    def __str__(self):
        if hasattr(self, 'name'):
            return self.name
        return self.atco_code


class Row(object):
    def append(self, row):
        row.next = self.next
        self.next = row

    def prepend(self, row):
        row.next = self

    def list(self):
        stop_ids = []
        row = self
        while row:
            stop_ids.append(row.atco_code)
            row = row.next
        return stop_ids

    def __init__(self, atco_code, times):
        self.next = None
        self.atco_code = atco_code
        self.part = Part(atco_code)
        self.times = times

    def __str__(self):
        string = ''
        p = self
        while p:
            string += '{} {}\n'.format(p.atco_code, [str(time)[:5] for time in p.times])
            p = p.next
        return string
