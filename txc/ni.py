import json
from datetime import date, datetime, timedelta


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
            yield self.date,


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

    def is_before(self, row):
        return row is not None and self.next is not None and (
            self.next.part.stop.atco_code == row.part.stop.atco_code
            or self.next.is_before(row)
        )

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


def contains(daterange, today):
    start = datetime.strptime(daterange['Start'], '%Y-%m-%d').date()
    end = datetime.strptime(daterange['End'], '%Y-%m-%d').date()
    return start <= today and end >= today


def should_show(journey, today):
    if not journey[today.strftime('%As')]:
        return False
    if not contains(journey, today):
        if journey['Exceptions']:
            for exception in journey['Exceptions']:
                if exception['Operation'] and contains(exception, today):
                    return True
        return False
    if journey['Exceptions']:
        for exception in journey['Exceptions']:
            if not exception['Operation'] and contains(exception, today):
                return False
    return True


def handle_journeys(journeys, today):
    i = 0
    head = None
    rows_map = {}

    for journey in journeys:
        if not should_show(journey, today):
            continue

        previous = None
        visited_stops = set()

        for stopusage in journey['StopUsages']:
            atco_code = stopusage['Location']
            if atco_code in rows_map:
                if atco_code in visited_stops:
                    if previous and previous.next and previous.next.atco_code == atco_code:
                        row = previous.next
                    else:
                        row = Row(atco_code, ['     '] * i)
                        previous.append(row)
                else:
                    row = rows_map[atco_code]
            else:
                row = Row(atco_code, ['     '] * i)
                rows_map[atco_code] = row
                if previous:
                    previous.append(row)
                else:
                    if head:
                        head.prepend(row)
                    head = row
            time = stopusage['Departure'] or stopusage['Arrival']
            row.times.append(time)
            row.part.timingstatus = 'PTP' if stopusage['TimingPoint'] == 'T1' else 'OTH'
            previous = row
            visited_stops.add(atco_code)

        if i:
            p = head
            while p:
                if len(p.times) == i:
                    p.times.append('     ')
                p = p.next
        i += 1
    p = head
    g = Grouping()
    while p:
        g.rows.append(p)
        p = p.next
    return g


def get_data(path):
    with open(path) as open_file:
        data = json.load(open_file)
    return (data['Outbound'], data['Inbound'])


def get_timetable(path, today):
    t = Timetable()

    outbound, inbound = get_data(path)

    t.groupings.append(handle_journeys(outbound['Journeys'], today))
    t.groupings[-1].name = outbound['Description']

    t.groupings.append(handle_journeys(inbound['Journeys'], today))
    t.groupings[-1].name = inbound['Description']

    t.date = today
    return [t]
